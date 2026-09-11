# Architecture

## Overview

```
                    ┌─────────────────────┐
  python -m bot.cli │   bot/orchestrator   │  1. place call (Twilio REST)
  call --scenario X │   + bot/telephony    │  2. poll until terminal status
                    └──────────┬───────────┘  3. download recording.mp3
                               │
                               ▼
                     ┌───────────────────┐
                     │   Twilio (PSTN)    │◄──── dials +1-805-439-8008
                     └─────────┬──────────┘
                               │ TwiML webhook (POST /twiml)
                               ▼
        ┌───────────────────────────────────────────┐
        │  bot/server.py  (FastAPI, public via ngrok) │
        │   /twiml          -> <Connect><Stream>       │
        │   /media-stream   -> websocket, per call      │
        └──────────────────────┬──────────────────────┘
                                │ Twilio Media Stream (G.711 mu-law)
                                ▼
                 ┌───────────────────────────────┐
                 │   bot/realtime_bridge.py        │
                 │   relays audio both directions   │
                 │   to/from OpenAI Realtime API     │
                 └───────────────┬────────────────┘
                                 │
                                 ▼
                   OpenAI Realtime API (speech-to-speech)
                   configured with the scenario's persona
                   as system instructions — this IS the
                   simulated "patient" on the call

  After the call:
    bot/bug_analyzer.py  -> reads transcript.json, scores it against the
                              scenario's expected behavior with a text
                              model, writes findings.json
    reports/BUG_REPORT.md <- aggregated from every data/calls/*/findings.json
```

## How the call actually happens

`bot/orchestrator.py` asks Twilio's REST API to dial the test number,
pointing Twilio's webhook at our own `/twiml` endpoint. Twilio fetches
that, gets back a `<Connect><Stream>` pointing at our `/media-stream`
websocket, and starts streaming the call's audio to us in real time as
base64-encoded G.711 mu-law frames. `bot/realtime_bridge.py` forwards
those frames directly into an OpenAI Realtime API session, and forwards
the Realtime API's generated audio back to Twilio to play into the call.
The Realtime session's system prompt is built from the chosen scenario
(`bot/personas.py`) — persona, goal, and behavioral rules — so the model
*is* the simulated patient for the duration of the call, not a script
being read out.

## Key design decision: Realtime API (speech-to-speech) vs. a
STT → LLM → TTS pipeline

This was the main architectural choice, and the two options were:

1. **Speech-to-speech via OpenAI's Realtime API** (what this repo does):
   audio in, audio out, one model, one persistent session.
2. **A classic pipeline**: transcribe Athena's audio with Whisper, feed
   the text to a chat model to decide what the patient says next,
   synthesize that with a TTS engine, and loop.

The pipeline approach is more flexible (you can log/inspect/intervene at
every text boundary, swap providers per stage, and it's the more
"traditional" architecture) but it adds real latency at every stage —
transcribe, then think, then synthesize — which shows up on a phone call
as unnatural pauses and makes barge-in/interruption handling much harder
to get right, since you're coordinating three separate systems' notion of
"who's talking now." The challenge brief explicitly calls out realistic
pacing, sensible turn-taking, and natural conversational quality as
priority evaluation criteria, which pushed this toward whichever
architecture would produce the *most natural-sounding call*, not the
most inspectable pipeline.

The Realtime API collapses all three stages into one model and one
WebSocket session, with built-in server-side voice activity detection
(turn_detection) and an audio format (`g711_ulaw`) that Twilio also
speaks natively — so audio is relayed with effectively zero transcoding
in `realtime_bridge.py`. Barge-in is handled by listening for
`input_audio_buffer.speech_started` and telling Twilio to `clear` its
queued playback, rather than building custom interruption logic across
three services. The tradeoff is less visibility into "what did the model
think it heard" at each intermediate step — mitigated here by still
capturing both sides' text via the Realtime API's own transcription
events (`response.audio_transcript.done` /
`conversation.item.input_audio_transcription.completed`), so the
transcript pipeline didn't need a separate STT pass either.

## Why bug analysis is a separate pass, not inline

`bot/bug_analyzer.py` runs *after* the call, as its own text-only model
call against the saved transcript — not something the Realtime session
does mid-conversation. Judging quality requires seeing the whole
conversation at once (e.g. "did the agent ever get back to the third
thing the patient asked for?") and works better with a plain reasoning
model than trying to multitask that judgment into the same session that's
busy holding a live voice conversation. It also makes the two concerns
independently testable and replayable: you can re-run the bug analyzer
against an old transcript without placing a new phone call, and the
analyzer's tests mock the OpenAI client entirely rather than needing a
live Realtime session.

The analyzer is deliberately narrow in scope, per the brief's own
"what we're not looking for" list — the prompt explicitly tells the model
to ignore phrasing/filler nitpicks and the caller's own behavior, to only
flag things that would matter to an actual patient, and that an empty
findings list is a perfectly good result for a clean call.

## Other choices

- **Twilio** for the PSTN leg: it's the de facto standard for
  programmable voice, has first-class dual-channel call recording, and
  its Media Streams protocol is exactly what the Realtime API's telephony
  audio format was designed to pair with.
- **Scenario-per-YAML-file** (`bot/personas.py` + `scenarios/*.yaml`)
  instead of hardcoding personas in Python: adding a new test case is a
  config change, not a code change, and each scenario carries its own
  `success_criteria`/`expected_agent_behavior` that both a human and the
  bug analyzer can read.
- **A tiny Node/Express dashboard**, not a database: it reads the same
  `data/calls/<id>/*.json` files the Python side already writes, so
  there's nothing to keep in sync — useful for quickly listening back and
  comparing transcripts while iterating on scenarios.
- **Explicit safety caps**: `MAX_CALL_DURATION_SECONDS` bounds any single
  call and `BATCH_CALL_DELAY_SECONDS` paces a batch run, since this bot
  places real, billed phone calls against someone else's live system.

## What's intentionally not here

Per the brief's own "what we're not looking for": no queueing
infrastructure, no persistent database, no multi-provider abstraction
layer over Twilio/OpenAI, no auth/multi-tenant dashboard. This is a
focused tool for one job — place realistic test calls against one number
and surface real bugs — not a production telephony platform.
