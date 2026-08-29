"""
Main server for the voice bot.
Handles Twilio webhooks - when someone picks up the phone, this server
figures out what to say back using the AI.
"""

import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import Response
from dotenv import load_dotenv

from voice_engine import generate_response, reset_conversation
from scenarios import get_scenario, list_scenarios

load_dotenv()

app = FastAPI(title="Pretty Good AI Voice Bot")

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")

# map scenario number to name (1 -> "scheduling", 2 -> "rescheduling", etc.)
SCENARIO_MAP = {i+1: name for i, name in enumerate(list_scenarios())}

# keeps track of state for each active call
call_states = {}

# twilio sometimes sends the same speech result twice, so we keep track
# of what we already processed to avoid duplicates
_last_speech = {}

# instead of a hard cut-off, Maria asks the other side whether they want
# to keep going once the call passes this many turns. "yes" resets the count.
TURN_LIMIT = 30

TURN_LIMIT_QUESTION = ("I've been on this call for a while now and I've reached "
                       "my 30-turn conversation limit. Do you still need to "
                       "keep talking with me, or should we wrap things up?")


def classify_continue(text):
    """
    After Maria asks about the turn limit, decide what the other side meant.
    Returns True to keep going, False to hang up, or None if unclear
    (in which case we refresh the count and keep going).
    """
    if not text:
        return None

    lower = text.lower()

    # clear "yes, keep going" answers
    yes_phrases = [
        "yes", "yeah", "sure", "go ahead", "continue", "keep going",
        "let's continue", "lets continue", "we can continue", "need to continue",
        "keep talking", "don't hang up", "stay on", "please do", "absolutely"
    ]
    for phrase in yes_phrases:
        if phrase in lower:
            return True

    # clear "no, we're done" answers
    no_phrases = [
        "that's all", "that is all", "thats all", "that's everything",
        "thats everything", "we're all set", "we are all set", "all set",
        "we're done", "we are done", "we're good", "we are good", "nothing else",
        "no further", "no more", "not needed", "don't need", "no thank",
        "no thanks", "we can end", "wrap up", "that's fine", "thats fine",
        "goodbye", "good bye", "bye"
    ]
    for phrase in no_phrases:
        if phrase in lower:
            return False

    # polite "no" that does NOT mean "end the call" - treat as unclear
    polite_no_phrases = ["no problem", "no worries", "no issue", "no big deal",
                         "no trouble", "no stress", "no concerns"]
    for phrase in polite_no_phrases:
        if phrase in lower:
            return None

    # single little word "no" - only match it on its own
    import re
    if re.search(r"\bno\b", lower):
        return False

    # could not tell - default to keeping the conversation going
    return None


def get_system_prompt(scenario_id=None):
    """Get the AI prompt for a given scenario."""
    if scenario_id:
        scenario_name = SCENARIO_MAP.get(scenario_id)
        if scenario_name:
            scenario = get_scenario(scenario_name)
            return scenario["prompt"]
    # default prompt if no scenario
    return ("You are Maria Santos, a 34-year-old patient calling a medical clinic. "
            "Have a natural conversation. Keep responses short (1-3 sentences). "
            "This is a phone call.")


def get_opening(scenario_id=None):
    """Get the first thing Maria says for each scenario."""
    if scenario_id:
        scenario_name = SCENARIO_MAP.get(scenario_id)
        if scenario_name:
            scenario = get_scenario(scenario_name)
            return scenario.get("opening", "Hi there! I'm calling to schedule an appointment.")
    return "Hi there! I'm calling to schedule an appointment."


def make_gather_twiml(text, action_url):
    """Make TwiML that speaks some text then listens for a response."""
    # need to escape XML characters so it doesn't break
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{text}</Say>
    <Gather input="speech" action="{action_url}" method="POST"
            speechTimeout="3" timeout="15" language="en-US" enhanced="true">
    </Gather>
</Response>"""


def make_say_twiml(text):
    """Make TwiML that just speaks text (no listening after)."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{text}</Say>
</Response>"""


@app.get("/")
async def root():
    return {"status": "healthy", "message": "Pretty Good AI Voice Bot is running"}


@app.post("/handle-call")
async def handle_call(request: Request):
    """
    Called by Twilio when the call first connects.
    We don't say anything yet - we just listen for the agent to greet us.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    from_number = form_data.get("From", "unknown")

    print(f"[Server] Call connected: {call_sid} from {from_number}")

    # figure out which scenario this is
    scenario_id_str = request.query_params.get("scenario_id", "1")
    try:
        scenario_id = int(scenario_id_str)
    except (ValueError, TypeError):
        scenario_id = 1

    system_prompt = get_system_prompt(scenario_id)
    reset_conversation()

    # save the greeting for later - we'll say it after the agent greets us
    greeting = get_opening(scenario_id)
    call_states[call_sid] = {
        "system_prompt": system_prompt,
        "turn_count": 0,
        "start_time": time.time(),
        "conversation": [],
        "greeting_pending": greeting,
        "empty_count": 0,
        "awaiting_transfer": False
    }

    # just listen - don't say anything yet
    action_url = f"{SERVER_URL}/gather-response?call_sid={call_sid}"
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="{action_url}" method="POST"
            speechTimeout="3" timeout="15" language="en-US" enhanced="true">
    </Gather>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@app.post("/gather-response")
async def gather_response(request: Request):
    """
    This is the main conversation loop. Twilio sends us what the agent said,
    we generate a response and send it back.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", request.query_params.get("call_sid", "unknown"))
    speech_result = form_data.get("SpeechResult", "")

    # check for duplicate (twilio sometimes sends same thing twice)
    now = time.time()
    if speech_result.strip():
        last = _last_speech.get(call_sid)
        if last and last[0] == speech_result and (now - last[1]) < 10:
            print(f"[Dedup] Skipping duplicate: {speech_result!r}")
            action_url = f"{SERVER_URL}/gather-response?call_sid={call_sid}"
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="{action_url}" method="POST"
            speechTimeout="3" timeout="15" language="en-US" enhanced="true">
    </Gather>
</Response>"""
            return Response(content=twiml, media_type="application/xml")
        _last_speech[call_sid] = (speech_result, now)

    print(f"[User] {speech_result}")

    state = call_states.get(call_sid, {})
    system_prompt = state.get("system_prompt", get_system_prompt())
    conversation = state.get("conversation", [])

    # first turn: agent just greeted us, now we say our opening line
    greeting_pending = state.get("greeting_pending")
    if greeting_pending:
        if speech_result.strip():
            _last_speech[call_sid] = (speech_result, now)
        response_text = greeting_pending
        state["greeting_pending"] = None
        if speech_result.strip():
            conversation.append({"role": "user", "content": speech_result})
        conversation.append({"role": "assistant", "content": response_text})
        state["conversation"] = conversation
        call_states[call_sid] = state

        print(f"[AI] {response_text}")
        action_url = f"{SERVER_URL}/gather-response?call_sid={call_sid}"
        twiml = make_gather_twiml(response_text, action_url)
        return Response(content=twiml, media_type="application/xml")

    # normal conversation turns
    if speech_result.strip():
        response_text = generate_response(speech_result, system_prompt)
        state["empty_count"] = 0
    else:
        # agent didn't say anything (or we couldn't hear them)
        empty_count = state.get("empty_count", 0) + 1
        state["empty_count"] = empty_count
        if empty_count >= 3:
            response_text = "I'm having trouble hearing you. I'll try calling back another time. Goodbye!"
        elif empty_count == 2:
            response_text = "I still can't hear you well. Could you speak a bit louder?"
        else:
            response_text = "Sorry, I didn't catch that. Could you say that again?"

    # count this turn
    state["turn_count"] = state.get("turn_count", 0) + 1

    # check if agent said they're transferring us - don't end call if so
    transfer_keywords = ["transfer", "let me check", "let me look", "hold on",
                         "one moment", "i'll find out", "let me see",
                         "put you through", "connect you", "supervisor",
                         "manager", "let me ask"]
    agent_transferring = False
    if speech_result:
        for kw in transfer_keywords:
            if kw in speech_result.lower():
                agent_transferring = True
                break

    if agent_transferring:
        state["awaiting_transfer"] = True
        call_states[call_sid] = state

    # check if we should end the call
    farewell_keywords = ["goodbye", "good bye", "bye", "thank you so much", "that's all"]
    maria_said_farewell = False
    for kw in farewell_keywords:
        if kw in response_text.lower():
            maria_said_farewell = True
            break

    is_farewell = maria_said_farewell and not state.get("awaiting_transfer")

    # check if agent confirmed we're done
    agent_done_keywords = ["you're all set", "have a great day"]
    agent_said_done = False
    if speech_result:
        for kw in agent_done_keywords:
            if kw in speech_result.lower():
                agent_said_done = True
                break

    if agent_said_done:
        state["awaiting_transfer"] = False
        call_states[call_sid] = state

    # ---- 30-turn limit handling ----
    # instead of a hard cut-off, Maria asks the other side whether they need
    # to keep going. "no" ends the call, "yes" resets the counter.
    end_call_now = False
    turn_check_pending = state.get("turn_check_pending", False)

    if turn_check_pending:
        # we asked about the turn limit last turn - this is the answer
        keep_going = classify_continue(speech_result)
        if keep_going is False:
            end_call_now = True
            response_text = ("Okay, we'll leave it there then. Thanks so much "
                             "for your help, goodbye!")
        else:
            # "yes" (or unclear) - refresh the counter and keep the call going
            state["turn_count"] = 0
            state["turn_check_pending"] = False
            call_states[call_sid] = state
    elif state["turn_count"] >= TURN_LIMIT:
        # hit the soft limit - ask before continuing instead of hanging up
        response_text = TURN_LIMIT_QUESTION
        state["turn_check_pending"] = True
        call_states[call_sid] = state

    print(f"[AI] {response_text}")

    # save the final version to the conversation log
    conversation.append({"role": "user", "content": speech_result})
    conversation.append({"role": "assistant", "content": response_text})

    state["conversation"] = conversation
    call_states[call_sid] = state

    # end the call if needed
    if end_call_now or is_farewell or agent_said_done:
        twiml = make_say_twiml(response_text)
        save_transcript(call_sid, conversation)
        _last_speech.pop(call_sid, None)
        return Response(content=twiml, media_type="application/xml")

    # otherwise keep listening
    action_url = f"{SERVER_URL}/gather-response?call_sid={call_sid}"
    twiml = make_gather_twiml(response_text, action_url)
    return Response(content=twiml, media_type="application/xml")


@app.post("/call-status")
async def call_status(request: Request):
    """Called by Twilio when the call status changes."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    status = form_data.get("CallStatus", "unknown")
    duration = form_data.get("CallDuration", "0")
    print(f"[Server] Call {call_sid} status: {status} (duration: {duration}s)")

    if status == "completed":
        state = call_states.pop(call_sid, {})
        conversation = state.get("conversation", [])
        # only save if not already saved
        if conversation:
            os.makedirs("transcripts", exist_ok=True)
            existing = [f for f in os.listdir("transcripts") if call_sid in f]
            if not existing:
                save_transcript(call_sid, conversation)
        _last_speech.pop(call_sid, None)

    return {"status": "ok"}


def save_transcript(call_sid, conversation):
    """Save the conversation to a text file."""
    os.makedirs("transcripts", exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    filename = f"transcripts/call_{call_sid}_{timestamp}.txt"

    with open(filename, "w") as f:
        f.write(f"Call SID: {call_sid}\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        for entry in conversation:
            role = entry["role"].upper()
            f.write(f"[{role}]: {entry['content']}\n\n")

    print(f"[Transcript] Saved to: {filename}")


def start_server(host="0.0.0.0", port=8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
