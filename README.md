# athena-voice-tester

An automated voice bot that calls Pretty Good AI's Athena test line,
plays a simulated "patient" through a realistic phone conversation,
records and transcribes both sides, and automatically flags quality bugs
in Athena's responses.

Built for the AI Engineering Challenge at Pretty Good AI — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how it works and why
it's built this way, and [`reports/BUG_REPORT.md`](reports/BUG_REPORT.md)
for findings from real calls.

## How it works, in one sentence

Twilio dials the test line and streams the call's audio to a small
FastAPI server over a websocket; that server bridges the audio directly
to the OpenAI Realtime API (configured with a per-scenario "patient"
persona), so the model has the actual spoken conversation with Athena —
no separate speech-to-text/LLM/text-to-speech pipeline, and no scripted
DTMF/text exchange.

## Project layout

```
bot/
  server.py          FastAPI app Twilio talks to (/twiml, /media-stream)
  realtime_bridge.py Twilio Media Stream <-> OpenAI Realtime audio bridge
  personas.py         Scenario loader (scenarios/*.yaml -> Scenario)
  telephony.py        Twilio REST helpers: place call, poll, fetch recording
  orchestrator.py      Drives one call / a full batch end to end
  bug_analyzer.py      LLM-judged transcript analysis -> findings.json
  transcript.py        Live transcript buffering + disk persistence
  config.py            Settings (.env)
  cli.py               `python -m bot.cli ...`
scenarios/            14 YAML test scenarios (see below)
dashboard/             Local Node/Express + vanilla JS UI for browsing calls
data/calls/<call_id>/  Per-call artifacts: recording.mp3, transcript.{json,txt},
                        metadata.json, findings.json
                        (gitignored during development; the calls you submit
                        must be force-added — see data/README.md)
reports/BUG_REPORT.md  Auto-aggregated bug findings across all calls
tests/                 pytest suite (mocks Twilio/OpenAI — no live calls needed to test)
```

## Setup

Requirements: Python 3.11+, Node 18+, a Twilio account + phone number, an
OpenAI API key with Realtime API access, and a way to expose a local port
publicly (e.g. [ngrok](https://ngrok.com)).

```bash
git clone https://github.com/clintonfezeu/athena-voice-tester.git
cd athena-voice-tester

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

### Getting your credentials

- **Twilio** — sign up at [twilio.com](https://www.twilio.com). Your
  `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are on the Console
  dashboard homepage. Under **Phone Numbers → Manage → Buy a number**,
  get one number to use as `TWILIO_FROM_NUMBER` — a trial number works
  fine for this.
- **OpenAI** — create a key at
  [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
  for `OPENAI_API_KEY`. Realtime API access is tied to your account's
  usage tier; if `gpt-realtime` isn't available yet, add a small amount
  of billing credit to unlock it.
- **ngrok** — sign up free at [ngrok.com](https://ngrok.com), install
  it, and run `ngrok config add-authtoken <your token>` once. From then
  on, `ngrok http 8000` gives you a public URL for `PUBLIC_BASE_URL`.

Twilio needs that public HTTPS/WSS URL to reach this app for TwiML and
the media stream. In one terminal:

```bash
ngrok http 8000
# copy the https://xxxx.ngrok-free.app URL it prints into .env as PUBLIC_BASE_URL
uvicorn bot.server:app --host 0.0.0.0 --port 8000
```

With that running, every call is a **single command** in a second terminal:

```bash
python -m bot.cli list-scenarios                              # see what's available
python -m bot.cli call --scenario simple_scheduling_new_patient  # one call
python -m bot.cli run-batch                                      # every scenario, paced
```

Each call's recording, transcript, and metadata land in
`data/calls/<call_id>/`. Then:

```bash
python -m bot.cli analyze-all   # LLM bug analysis for every call with a transcript
python -m bot.cli build-report  # regenerate reports/BUG_REPORT.md
```

Browse everything visually:

```bash
cd dashboard && npm install && npm start
# open http://localhost:4000
```

## Test scenarios

14 scenarios in [`scenarios/`](scenarios/), covering every category the
challenge brief asks for:

| Category | Scenarios |
|---|---|
| Scheduling | new patient booking, returning patient booking |
| Rescheduling | move an existing appointment, cancel outright |
| Refills | medication refill request |
| Information | office hours, location/parking, insurance coverage |
| Edge cases | barge-in/interruption, vague request, out-of-hours booking, multiple stacked requests, correcting misheard info, frustrated/urgent caller |

Add a new one by dropping a YAML file in `scenarios/` — see any existing
file for the shape (`bot/personas.py` validates required fields at load
time).

## Development

```bash
ruff check bot tests   # lint
pytest                 # unit tests (fully mocked — no API keys or live calls needed)
```

CI (`.github/workflows/ci.yml`) runs both, plus a dashboard install +
smoke test, on every PR.

A `Makefile` wraps the common commands (`make install`, `make server`,
`make call SCENARIO=...`, `make batch`, `make analyze`, `make report`,
`make dashboard`, `make test`, `make lint`) if you'd rather not type the
full `python -m bot.cli ...` invocations.

## Environment variables

See [`.env.example`](.env.example) for the full list with comments.
Never commit `.env` — it's gitignored.

## Submitting your calls

`data/calls/` is gitignored during development (so iterating doesn't
spam the repo with throwaway test calls), but the challenge requires the
final recordings + transcripts to actually be in GitHub. Once you have
your 10+ real calls:

```bash
git add -f data/calls/<call_id_1> data/calls/<call_id_2> ...   # or -f data/calls to add them all
git commit -m "docs: add submission call recordings and transcripts"
python -m bot.cli build-report   # regenerate reports/BUG_REPORT.md from the final set
```

See [`data/README.md`](data/README.md) for the exact per-call file layout.

## Submission checklist

- [ ] Add Twilio + OpenAI credentials to `.env` and run the batch (or
      individual scenarios) against the live test line
- [ ] Review the recordings and transcripts, pick the 10+ calls to
      submit, and commit them (see "Submitting your calls" above)
- [ ] Run `analyze-all` and `build-report`, then give
      `reports/BUG_REPORT.md` a final read-through
- [ ] Record the two Loom videos — project walkthrough, and an AI
      debugging session
- [ ] Note the phone number used for testing, in E.164 format
- [ ] Submit the form: repo link, both Loom links, and that phone number

## Cost & safety notes

- `MAX_CALL_DURATION_SECONDS` hard-caps any single call.
- `BATCH_CALL_DELAY_SECONDS` paces calls in a batch run instead of
  hammering the test line back to back.
- All calls dial exactly `TARGET_NUMBER` (`+1-805-439-8008`, fixed by the
  assessment) — this is not a general-purpose autodialer.
