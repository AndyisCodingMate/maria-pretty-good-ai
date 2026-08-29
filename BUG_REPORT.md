# Bug Report - Pivot Point Orthopedics AI Agent

10 test calls were placed against the test line (+1-805-439-8008) with the bot
acting as patient **Maria Santos**. Each call was recorded and transcribed.
This report documents the most important issues found, ordered by real-world
impact. Quotes are taken from the transcripts in `transcripts/`.

**Call reference** (scenario → call SID → transcript file):

| # | Scenario | Transcript |
|---|----------|-----------|
| 1 | Scheduling | `call_CA168064f724b441bc9cb68620e15cc983_*` |
| 2 | Rescheduling | `call_CA1deff2badb3171e46650d248f7e925df_*` |
| 3 | Cancellation | `call_CAc2368f4869490e7f06c81cdded28554c_*` |
| 4 | Medication refill | `call_CA106750ee789e4aa5fac55a0a2ac6d285_*` |
| 5 | Office hours | `call_CA5ecb4d8f58e6b770179e88e6eb684642_*` |
| 6 | Insurance | `call_CA349ab88a2a160916245e1f7630cd0703_*` |
| 7 | Interruption | `call_CAf6f10454f288e3dcbb71af100ebda0d3_*` |
| 8 | Unclear request | `call_CA139cb9d229fcd38dd71c45f593acf0db_*` |
| 9 | Off-script | `call_CAe18b389f14a0b79258565a0a69424c49_*` |
| 10 | Emotional | `call_CA055d1990ef36a9fa4319204e9d5cdac7_*` |

---

## Bug 1 — Agent tells the patient she is in "demo" mode
**Severity: High**
**Call:** 6 (Insurance, `call_CA349ab88a2a160916245e1f7630cd0703_*`)

**What happened:**
> USER: "Please provide your date of birth."
> ASSISTANT: "My date of birth is March 12, 1990."
> USER: "The birthday doesn't match our records **but for demo purposes I'll accept it.** Let me check your insurance question now."

**Why it's a problem:** A real patient would never expect, and would be alarmed
by, an agent that announces it is running in "demo mode." This leaks internal
test/infrastructure context into the caller-facing conversation, undermines
trust, and suggests that environment flags are bleeding into the agent's prompt
or behavior. Should read something neutral like "I wasn't able to match the
date of birth on file, but I'll continue to help you."

---

## Bug 2 — Promised "transfer to patient support" is a dead end
**Severity: High**
**Call:** 1, 2, 3, 4, 10

**What happened:** Whenever the patient needed something the agent couldn't do,
it offered a warm handoff, then delivered none:
> USER: "Yes, please connect me to patient support." (call 2)
> AGENT: "Transferring you now. Thank you. **Hello, you've reached the pretty good AI test line, goodbye.**"

The same pattern appears at the end of calls 1, 3, 4, and 10. After promising
"let me connect you," the agent plays a generic recording and the call ends.

**Why it's a problem:** The patient's actual request — reschedule, cancel,
refill — is never resolved. From the patient's perspective the agent promised a
person who could help and then dropped the call. This is the single biggest
reason the "task completion" bar isn't met for those scenarios. If transfers
are not available in this environment, the agent should say so honestly and
offer a callback/timeframe instead of claiming a handoff it won't perform.

---

## Bug 3 — Redundant identity re-verification loop
**Severity: Medium**
**Call:** 2, 3, 4, 10

**What happened:** After the patient gives name + DOB and the agent repeats
them back and gets confirmation, the agent still demands spelling — and in
call 3 asks for it twice:
> AGENT: "Just to confirm, I have your name as Maria Santos and your date of
> birth as March 12th 1990. Is that correct? **If so, please spell your first
> and last name for me?**"
> ASSISTANT: "M-A-R-I-A S-A-N-T-O-S."
> AGENT: "Thanks, could you please spell your last name **1 more time** just
> to be sure I have it right?"

**Why it's a problem:** Pointless back-and-forth. The data was already
confirmed verbatim, so re-asking for spelling (twice) wastes the patient's
time and feels interrogative. Verification should stop once the agent has
confidence (matched phone number + confirmed name + confirmed DOB).

---

## Bug 4 — Agent cuts the patient off mid-spell and asks her to redo it
**Severity: Medium**
**Call:** 2 (Rescheduling, `call_CA1deff2badb3171e46650d248f7e925df_*`)

**What happened:**
> ASSISTANT: "...S as in Sierra, A as in Alpha, N as in November, T as in
> Tango, O as in Oscar, S as..."
> USER: "Could you please **finish spelling your last name**? ... It seems to
> have cut off."

**Why it's a problem:** The agent interrupted the patient before she finished
and then made her restart the spelling. Beyond the wasted round-trip, it shows
turn-taking that doesn't wait for a natural utterance boundary — the agent
should let a speaker finish before processing.

---

## Bug 5 — "I can't find your record" dead end after identity was verified
**Severity: Medium**
**Call:** 2, 3

**What happened:** After name, DOB, and phone number were all given and
confirmed by the agent:
> AGENT: "I'm unable to find your record in our system so I can't reschedule
> your appointment right now. I can connect you to our patient support team."

**Why it's a problem:** Combined with Bug 2, the patient can never actually
reschedule or cancel — the agent confirms it has the identifiers, then gives
up and escalates to a handoff that also fails. For a production product, an
"unable to find record" path should have a recovery strategy (re-entering info,
checking alternate records, or a concrete callback) rather than a loop that
routes straight to a dead-end transfer.

---

## Bug 6 — Identifier read-back gets garbled
**Severity: Low**
**Call:** 3, 4

**What happened:** When the agent reads the patient's phone number back to
confirm it, the speech comes across broken or mis-worded:
> Call 4: "I have **your photographs** 1682 3562228 and your date of birth as
> March 12th 1990. Is that correct?"
> Call 3: "I have your phone number as **1682356. 2228**..."

**Why it's a problem:** If the agent genuinely said "photographs," that's a
disallowed subject change mid-task; if it's upstream ASR mangling the output,
then the read-back is unreliable and patients are forced to repeat their
identifiers. Either way, sensitive identity read-backs should be crisp and
verbatim.

---

## What went right (and should be preserved)

- **Interruption handling (call 7):** The patient paused mid-sentence
  ("someone's at my door"), and the agent waited, came back to the exact topic,
  and completed the booking. This is the ideal behavior.
- **Out-of-scope deflection (call 9):** Asked for dog vitamins, the agent
  politely declined, recommended the vet, and ended smoothly.
- **Scope honesty (call 1):** When asked for a primary-care checkup at an
  orthopedics clinic, the agent correctly redirected instead of overbooking.
- **Consistent office-hours info (call 5):** Open M–F, closed weekends, no
  after-hours on-call — no contradictions across the conversation.

## System note (our side, for transparency)

Several calls end with our bot saying "Sorry, what was that?" (calls 2, 3, 4,
9, 10) — that's our capture loop failing to catch the agent's very last
utterance when it speaks and hangs up quickly. It is worth noting as a
measurement limitation, not an agent bug, and is largely caused by the
transfer/dead-end behavior in Bug 2 ending those calls abruptly.