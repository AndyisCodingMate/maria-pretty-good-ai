# Loom Video 1 — Project Walkthrough Script (max 3:00)

**Before you record:**
- Webcam **ON**, video visible, you speaking in your own voice.
- Screen-share your editor / repo when noted below.
- Read naturally — do NOT rush. Pauses are fine.
- Total script is ~430 words ≈ 2:45–3:00 when spoken at a normal pace.

---

**[0:00–0:15] Intro — hook (webcam only)**
> "Hi, I'm Andy. I built MARIA — a voice bot that acts as a patient named Maria
> Santos and calls Pretty Good AI's clinic line to stress-test their AI
> receptionist. She schedules appointments, cancels, asks awkward questions,
> and finds bugs — all by having real phone conversations. This is how it works."

---

**[0:15–0:55] Approach — why this design (screen: architecture or repo overview)**
> "The obvious way to build a voice bot is a real-time speech-to-speech API.
> I deliberately didn't do that. Real-time APIs are expensive, hard to run from
> a laptop, and honestly overkill for a normal telephone call — because the phone
> network is already synchronous. Instead I let Twilio do the speech work.
> Twilio's voice engine can recognize speech and cancel echo natively on their
> infrastructure. That means my server is just a simple request-response loop —
> no websockets, no audio streaming to debug. It also keeps the cost down to
> basically just the Twilio minutes."

---

**[0:55–1:35] How a call actually flows (screen: main.py + run_all.py)**
> "Here's what happens on every call. `run_all.py` starts a web server and a
> free Cloudflare tunnel so Twilio can reach me. For each of the ten scenarios,
> Twilio places a real call to the clinic. When their AI answers, it hears Maria
> greet it — her opening line is driven by one of ten scenario prompts. Their AI
> replies, Twilio transcribes it and sends it to my server. My server hands that
> to Groq — the model pretending to be Maria — it decides her next line, Edge TTS
> turns it into audio, and Twilio plays it back. Every turn is just this loop.
> When the call ends, the audio and a full transcript are saved automatically."

---

**[1:35–2:10] What a call found (screen: BUG_REPORT.md or a transcript)**
> "The point of all this was finding the product's limits — and we found some.
> In one call, the agent literally told the patient, quote, 'for demo purposes
> I'll accept it,' which no real patient should ever hear. In several calls, the
> agent promised to transfer to patient support and then the call just ended —
> the patient never got their cancellation or refill. Those are the kind of
> trust-breaking issues you only catch by hearing the full conversation."

---

**[2:10–2:40] Iteration — evidence I improved it (screen: git log)**
> "I also used the recordings to fix the bot itself. The first few calls had
> duplicate responses and the call hung up out of nowhere. I found that Twilio
> sometimes re-sends the same transcription, so I added de-duplication. I taught
> Maria to recognize when the agent says *I'll transfer you* so she doesn't hang
> up mid-task. And instead of cutting a long call at a hard turn limit, Maria now
> asks 'do you still need me?' and the counter resets if they say yes."

---

**[2:40–3:00] Wrap (webcam only)**
> "The whole thing is one command to run — `python3 run_all.py` — and there's a
> custom mode where you can write your own scenario and let Maria autopilot it.
> Full transcripts, recordings, and the bug report are in the repo. Thanks for
> watching — happy to talk through the details."