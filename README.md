# MARIA - Voice Bot Test Caller for Pretty Good AI 

MARIA, a Python voice bot that calls the Pivot Point Orthopedics test line (+1-805-439-8008)
and plays the part of a patient named **Maria Santos** across 10 realistic test scenarios.

The bot is designed to find bugs in the clinic's AI receptionist by having natural,
realistic phone conversations, then recording and transcribing every call for review.

## How it works (30 second version)

1. `run_all.py` starts a local web server and a public tunnel.
2. For each scenario, it uses **Twilio** to place a real phone call.
3. When the clinic's AI answers, it hears Maria greet it (text-to-speech via **Edge TTS**).
4. The clinic's AI replies, and **Twilio** captures that speech and sends it to our server.
5. Our server passes what was said to the **Groq** LLM (still playing Maria), and
   speaks her reply back over the phone.
6. Every call is recorded and transcribed automatically.
7. At the end you get a summary of all 10 calls plus the audio/transcripts to review.

## What's in this repo

| File | What it does |
|------|-------------|
| `run_all.py` | One command to run everything: tunnel + server + all 10 calls |
| `run_scenarios.py` | Same as above, but you pick which scenarios to call — or write your own |
| `custom_scenario.json` | Your custom scenario (created when you use custom mode; not committed) |
| `main.py` | FastAPI server that handles the call conversation loop |
| `voice_engine.py` | Talks to Groq (LLM) and Edge TTS (text-to-speech) |
| `scenarios.py` | The 10 test scenarios + Maria's personality rules |
| `chat.py` | Optional text-only chat tester (no phone call needed) |
| `transcripts/` | Text transcripts of every call (both sides) |
| `recordings/` | OGG audio recordings of every call |
| `results/` | JSON summary of each test run |

## Requirements

Before `run_all.py` will work, you need three things installed:

| What | Why | Install |
|------|-----|---------|
| **Python 3.10+** | The bot is written in Python | [python.org](https://www.python.org/downloads/) |
| **Python packages** | The libraries the code imports | See list below |
| **`cloudflared`** | Creates the public HTTPS tunnel Twilio talks to | See system tools below |
| **`ffmpeg`** | Converts call recordings to OGG format | See system tools below |

> **Note for Ubuntu/Debian:** when installing the Python packages, you may see an
> error about externally‑managed environments. If so, use:
> `pip install --user --break-system-packages -r requirements.txt`

### Python packages (from `requirements.txt`)

```bash
pip install -r requirements.txt
```

| Package | What the bot uses it for |
|---------|--------------------------|
| `fastapi` + `uvicorn` | The web server that receives Twilio's webhooks |
| `twilio` | Placing phone calls and downloading recordings |
| `groq` | The AI that decides what Maria says next |
| `edge-tts` | Turning Maria's lines into spoken audio |
| `python-dotenv` | Loading secrets from `.env` |
| `requests` | Downloading call recordings from Twilio |
| `websockets`, `aiohttp` | Extra HTTP/WebSocket support |

### System tools (needed besides the Python packages)

These are command-line tools, not Python packages.

**`cloudflared`** — required, Twilio cannot call your laptop without a public URL.

```bash
# Ubuntu/Debian
sudo apt install cloudflared

# macOS (Homebrew)
brew install cloudflared

# Other systems: https://developers.cloudflare.com/cloudflared/quickstart/
```

**`ffmpeg`** — required, converts the recorded calls from WAV to OGG.

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS (Homebrew)
brew install ffmpeg

# Other systems: https://ffmpeg.org/download.html
```

### Accounts and API keys (go in `.env`)

- **Twilio** — account SID, auth token, and a phone number with credit
  ([twilio.com/console](https://console.twilio.com))
- **Groq** — a free API key ([console.groq.com](https://console.groq.com))

## Setup

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd pretty_good_AI_project

# 2. Install the Python packages (see Requirements above)
pip install -r requirements.txt

# 3. Make sure cloudflared and ffmpeg are installed (see Requirements above)

# 4. Create your .env file
cp .env.example .env
# ... then edit .env with your real Twilio and Groq credentials

# 5. Start the bot (server + tunnel + all 10 calls)
python3 run_all.py
```

`run_all.py` handles starting the server, creating the tunnel
(a URL comes out and is written back into your `.env`), placing all
10 calls, and saving the transcripts + recordings into `transcripts/` and
`recordings/`.

> Note: each time the tunnel restarts the URL changes, so `run_all.py`
> updates `SERVER_URL` in `.env` automatically. No manual steps needed.

### Running a custom set of scenarios

Don't want to run all 10 calls? Use `run_scenarios.py` — same tunnel/server
setup, but you choose which scenarios to call:

```bash
# pick from an interactive menu
python3 run_scenarios.py

# run specific ones by number
python3 run_scenarios.py 1 3 5

# a range works too
python3 run_scenarios.py 2-4

# or everything
python3 run_scenarios.py all
```

### Writing your own custom scenario (autopilot mode)

You can also invent your own scenario and let Maria autopilot it — useful for
testing the clinic's AI with a situation that isn't in the default 10.

```bash
python3 run_scenarios.py custom
```

It asks for three things:

1. **Opening line** — what Maria says first when the clinic answers
2. **Scenario name** — just a label (optional)
3. **Instructions** — who Maria is and what her goal is (type `DONE` on its
   own line when finished)

Example:

```
Maria's opening line: Hi, I think I was double-charged on my last visit.

Type Maria's instructions below ... type DONE on its own line when finished:
You are a frustrated but polite patient who was billed twice for a visit.
You want a refund and you want to know when it will appear.
DONE
```

The instructions are saved to `custom_scenario.json` (not committed to git),
the shared "stay in character" rules are appended automatically, and Maria
then calls the clinic and plays out that scenario. It works anywhere a scenario
number is expected — `run_scenarios.py custom` and `run_scenarios.py 0 5` both
run your custom scenario (id `0`) plus the numbered ones.

## The 10 test scenarios

1. **Scheduling** - a new patient booking a first appointment
2. **Rescheduling** - work conflict, needs a new time
3. **Cancellation** - family obligation, worried about fees
4. **Medication refill** - running low, needs a refill
5. **Office hours** - when are you open, weekends, after-hours care
6. **Insurance** - is Blue Shield of California accepted, co-pay, referrals
7. **Interruption** - doorbell rings mid-call, resumes where she left off
8. **Unclear request** - vague fatigue complaint, agent must ask questions
9. **Off-script** - asks about dog vitamins, tests graceful deflection
10. **Emotional** - anxious first-time patient who needs reassurance

## Testing without making phone calls

A text-only test console was also created, 'chat.py', to test the AI responses
without using call credits. Individual calls can be made with different set scenarios
and an option to make all 10 calls in a row is also available.

```bash
python3 chat.py
```

Pick a scenario and type back and forth with Maria in your terminal.

## Outputs

After a run you get:

- `results/run_<timestamp>.json` - what happened on each call
- `transcripts/call_<sid>_<timestamp>.txt` - both sides of every conversation
- `recordings/<call_sid>.ogg` - audio for every call

Use those to review Maria's conversations and find bugs in the clinic's AI.