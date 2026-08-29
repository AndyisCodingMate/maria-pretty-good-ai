# Call Log - 10 Test Scenarios

All calls were made to **+1-805-439-8008** from Twilio number **+16823562228**
using patient persona **Maria Santos** (DOB 03/12/1990, phone +1-682-356-2228,
insurance Blue Shield of California).

Every call completed in full and was recorded. See `transcripts/` for the text
of both sides of each conversation and `recordings/` for the OGG audio.

| # | Scenario | Duration | Status | Recording (OGG) | Transcript |
|---|----------|----------|--------|-----------------|------------|
| 1 | Scheduling a new appointment | 3m 09s | completed | `recordings/CA168064f724b441bc9cb68620e15cc983.ogg` | `transcripts/call_CA168064f724b441bc9cb68620e15cc983_*.txt` |
| 2 | Rescheduling | 2m 56s | completed | `recordings/CA1deff2badb3171e46650d248f7e925df.ogg` | `transcripts/call_CA1deff2badb3171e46650d248f7e925df_*.txt` |
| 3 | Cancellation | 2m 50s | completed | `recordings/CAc2368f4869490e7f06c81cdded28554c.ogg` | `transcripts/call_CAc2368f4869490e7f06c81cdded28554c_*.txt` |
| 4 | Medication refill | 2m 22s | completed | `recordings/CA106750ee789e4aa5fac55a0a2ac6d285.ogg` | `transcripts/call_CA106750ee789e4aa5fac55a0a2ac6d285_*.txt` |
| 5 | Office hours | 2m 11s | completed | `recordings/CA5ecb4d8f58e6b770179e88e6eb684642.ogg` | `transcripts/call_CA5ecb4d8f58e6b770179e88e6eb684642_*.txt` |
| 6 | Insurance inquiry | 1m 52s | completed | `recordings/CA349ab88a2a160916245e1f7630cd0703.ogg` | `transcripts/call_CA349ab88a2a160916245e1f7630cd0703_*.txt` |
| 7 | Interruption handling | 3m 34s | completed | `recordings/CAf6f10454f288e3dcbb71af100ebda0d3.ogg` | `transcripts/call_CAf6f10454f288e3dcbb71af100ebda0d3_*.txt` |
| 8 | Unclear request | 3m 42s | completed | `recordings/CA139cb9d229fcd38dd71c45f593acf0db.ogg` | `transcripts/call_CA139cb9d229fcd38dd71c45f593acf0db_*.txt` |
| 9 | Off-script (dog vitamins) | 0m 57s | completed | `recordings/CAe18b389f14a0b79258565a0a69424c49.ogg` | `transcripts/call_CAe18b389f14a0b79258565a0a69424c49_*.txt` |
| 10 | Emotional patient | 2m 12s | completed | `recordings/CA055d1990ef36a9fa4319204e9d5cdac7.ogg` | `transcripts/call_CA055d1990ef36a9fa4319204e9d5cdac7_*.txt` |

**Summary:** 10/10 calls completed, average call length ~2m 37s. Detailed
analysis of agent behavior is in `BUG_REPORT.md`.