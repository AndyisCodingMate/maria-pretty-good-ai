"""
This file handles talking to the AI and turning text into speech.
Uses Groq for the language model and Edge TTS for text-to-speech.
"""

import os
import asyncio
import tempfile
from groq import Groq
from dotenv import load_dotenv
import edge_tts

load_dotenv()

# connect to Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-120b"

# this keeps track of the conversation for each call
# (we reset it for each new call)
conversation_history = []


def reset_conversation():
    """Clear the conversation history for a new call."""
    global conversation_history
    conversation_history = []
    print("[Voice] Reset conversation history")


def clean_response(text):
    """Remove weird stuff that the model sometimes puts in its output."""
    if not text:
        return ""

    import re
    # remove <thinking>...</thinking> blocks
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
    # remove "thought" sections
    text = re.sub(r"thought\s*:.*$", "", text, flags=re.DOTALL | re.IGNORECASE)
    # remove leftover bracket tags like [done]
    text = re.sub(r"\[.*?\]\s*$", "", text)
    text = text.strip()

    return text


def truncate_sentences(text, max_length=300):
    """Cut the text at a natural sentence boundary so it's not too long."""
    if not text or len(text) <= max_length:
        return text

    # try to cut at a period
    idx = text[:max_length].rfind(".")
    if idx > max_length * 0.4:
        return text[:idx + 1].strip()

    # try comma
    idx = text[:max_length].rfind(",")
    if idx > max_length * 0.5:
        return text[:idx].strip() + "."

    # just cut it off
    return text[:max_length].strip()


def generate_response(user_message, system_prompt):
    """
    Send what the user said to the AI and get a response back.
    This is the main function that connects to Groq.
    """
    global conversation_history

    # add the system prompt as the first message
    if not conversation_history:
        conversation_history.append({
            "role": "system",
            "content": system_prompt
        })

    # add what the user (agent) just said
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    # keep the conversation from getting too long (last 10 turns)
    if len(conversation_history) > 20:
        conversation_history = [conversation_history[0]] + conversation_history[-18:]

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=conversation_history,
            max_tokens=150,
            temperature=0.7,
            stop=["\nUser:", "\nAgent:", "<thinking>", "[done]"]
        )

        response_text = response.choices[0].message.content
        response_text = clean_response(response_text)
        response_text = truncate_sentences(response_text)

        # save the AI's response in the conversation
        conversation_history.append({
            "role": "assistant",
            "content": response_text
        })

        print(f"[Voice] LLM response: {response_text}")
        return response_text

    except Exception as e:
        print(f"[Voice] Error: {e}")
        # clear conversation on error so we don't get stuck
        conversation_history.clear()
        return "Sorry, I'm having a little trouble. Could you repeat that?"


async def text_to_speech(text):
    """Convert text to audio using Edge TTS. Returns path to MP3 file."""
    if not text:
        return None

    audio_file = os.path.join(tempfile.gettempdir(), "tts_output.mp3")
    communicate = edge_tts.Communicate(text, voice="en-US-JennyNeural")
    await communicate.save(audio_file)

    print(f"[Voice] TTS saved to: {audio_file}")
    return audio_file


def mp3_to_mulaw(mp3_path, output_path):
    """Convert MP3 to mulaw WAV format that Twilio expects."""
    if not mp3_path or not os.path.exists(mp3_path):
        return None

    ffmpeg = os.path.expanduser("~/.local/bin/ffmpeg")

    cmd = [
        ffmpeg,
        "-i", mp3_path,           # input file
        "-ar", "8000",            # sample rate (twilio needs 8kHz)
        "-ac", "1",               # mono
        "-f", "wav",              # output format
        "-acodec", "pcm_mulaw",   # mulaw codec
        output_path
    ]

    import subprocess
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"[Voice] Converted to mulaw: {output_path}")
    return output_path


async def process_audio(text, system_prompt):
    """
    Full pipeline: take text input, get AI response, convert to audio.
    Returns the path to the audio file.
    """
    # get the AI's response
    response = generate_response(text, system_prompt)

    # convert to speech
    audio_path = await text_to_speech(response)

    return audio_path, response
