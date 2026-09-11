# data/calls/

Every call produces one directory here, named `<scenario_id>-<8 hex
chars>`:

```
data/calls/simple_scheduling_new_patient-a1b2c3d4/
  recording.mp3      dual-channel recording of the call (Twilio)
  transcript.json     structured turns: [{speaker, text, timestamp}, ...]
  transcript.txt      the same transcript, human-readable
  metadata.json        call_sid, status, to/from numbers, duration, timestamps
  findings.json        bug-analyzer output for this call (after `analyze-all`)
```

`speaker` in the transcript is either:
- `patient_bot` — our simulated caller (OpenAI Realtime, played from the
  scenario's persona)
- `athena_agent` — the real Pretty Good AI agent under test

## Why this is gitignored by default

During development you'll place far more than 10 calls while iterating on
scenarios and prompts — committing every one would bloat the repo with
throwaway audio. `data/calls/*` is gitignored (`data/calls/.gitkeep` keeps
the empty directory tracked) so local runs stay out of git automatically.

## Before submitting

The challenge requires the actual recordings and transcripts to be in the
GitHub repo. Once you've settled on the final set of calls to submit
(minimum 10, each a real conversation — not a single question and
hang-up), force-add them past the gitignore rule:

```bash
git add -f data/calls/<call_id>          # one call
git add -f data/calls                    # or everything currently in data/calls/
git commit -m "docs: add submission call recordings and transcripts"
```

Then regenerate the aggregated report from that final set:

```bash
python -m bot.cli build-report
```
