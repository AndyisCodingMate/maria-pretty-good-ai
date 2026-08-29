# Architecture

## Overview

The system is a **patient simulator** that calls the Pretty Good AI test line
(+1-805-439-8008) using Twilio and holds natural, goal-driven phone
conversations while acting as a patient named Maria Santos.

The architecture is deliberately simple:

```
run_all.py ──► Twilio API ──► phone call to Pivot Point Orthopedics
    │                                 │
    │                         clinic's AI answers
    │                                 │
    └─► FastAPI server  ◄── Twilio webhook (agent's speech)
            │
            ├─► Groq LLM  (decides what Maria says next)
            └─► Edge TTS  (turns it into spoken audio)
                    │
                    └─► Twilio plays it back over the call
```

## Key design decisions

**Why not a Realtime API?** The obvious approach for a voice AI is a
low-latency streaming/speech-to-speech API (like OpenAI Realtime or a
WebSocket pipeline). We deliberately avoided that. It costs more money
(a hard constraint here), it is harder to run reliably from a laptop, and
the test line is fully synchronous telephony anyway. Instead we let Twilio
be the speech engine: Twilio's `<Gather input="speech">` natively performs
speech recognition, echo cancellation, and turn-taking on its own
infrastructure. That removes an entire class of audio glitches (echoes,
overlapping speech) before we write any code. **We estimate this choice
eliminated most of the setup complexity and audio-quality bugs** that plague
DIY streaming setups.

**Turning a phone call into HTTP** is the core trick. Each turn is two
webhooks: Twilio transcribes whatever the agent said and POSTs it to our
FastAPI server (`/gather-response`); our server asks Groq "if you are Maria
Santos, how do you reply to that?", converts the answer to audio with Edge
TTS, and returns it as TwiML so Twilio speaks it. The whole system is just a
request/response loop, so it is stateless per turn, easy to debug from the
terminal log, and cheap (Groq has a generous free tier; Twilio minutes are
the only real cost).

**Why Edge TTS?** Free, no API key, low latency, and it runs locally on the
server, so there is no extra per-call fee on top of Twilio. It produces a
natural-sounding female voice (Jenny) that fits the Maria persona.

**Why a tunnel?** Twilio must be able to reach our server over the public
internet. Running code on a laptop, a `cloudflared` quick tunnel is the
simplest zero-config way to get a public HTTPS URL, and Twilio can POST
webhooks to it immediately.

**Turn-taking and termination.** Maria never ends the call herself. The
rules in `scenarios.py` make her bounce the conversation back until the
clinic's AI confirms the task is done (e.g., "You're all set"). A small
state machine tracks turns, detects when the agent says it will transfer
the call, and only hangs up on a confirmed farewell. Long calls aren't cut
off abruptly: once a call passes 30 turns, Maria asks the agent whether it
still needs to continue; a "no" ends the call, a "yes" resets the counter
and keeps the loop going.

**Custom scenarios.** A scenario is just data — a prompt (what Maria should
say and do) plus an opening line — so new ones need no code changes.
`run_scenarios.py custom` lets a user write their own prompt interactively,
saves it to `custom_scenario.json`, and the server treats it as scenario id
0 at the same `/handle-call` webhook. This is how edge cases beyond the
default 10 (billing complaints, unusual requests, etc.) get tested.

The result is a system that behaves like a real (if persistent) patient:
it answers verification questions correctly, steers every call toward its
goal, survives interruptions, and produces full transcripts plus clean
OGG recordings for every call.