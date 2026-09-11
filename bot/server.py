"""FastAPI app Twilio talks to: TwiML webhook + the media-stream websocket.

Call flow:
  1. `bot.telephony.place_call()` asks Twilio to dial `TARGET_NUMBER`,
     pointing its status webhook at `POST /twiml?scenario_id=...&call_id=...`.
  2. Twilio fetches `/twiml`, we return a `<Connect><Stream>` pointing back
     at our own `/media-stream` websocket (same scenario_id/call_id carried
     through as query params on the stream URL).
  3. Twilio opens the websocket and starts streaming call audio; `/media-stream`
     hands it off to a `RealtimeBridge` for the life of the call.
  4. On disconnect, the accumulated transcript is written to
     `data/calls/<call_id>/`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from bot.config import get_settings
from bot.personas import ScenarioError, get_scenario
from bot.realtime_bridge import RealtimeBridge
from bot.transcript import TranscriptRecorder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CALLS_DIR = Path("data/calls")

app = FastAPI(title="athena-voice-tester")


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/twiml")
async def twiml(request: Request) -> Response:
    scenario_id = request.query_params.get("scenario_id", "")
    call_id = request.query_params.get("call_id") or str(uuid4())
    settings = get_settings()

    stream_url = f"{settings.websocket_url}?scenario_id={scenario_id}&call_id={call_id}"
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f'<Stream url="{stream_url}" />'
        "</Connect></Response>"
    )
    return Response(content=body, media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket) -> None:
    scenario_id = websocket.query_params.get("scenario_id", "")
    call_id = websocket.query_params.get("call_id") or str(uuid4())
    settings = get_settings()

    try:
        scenario = get_scenario(scenario_id)
    except ScenarioError:
        logger.error("Rejecting media stream: unknown scenario_id=%r", scenario_id)
        await websocket.close(code=1008)
        return

    recorder = TranscriptRecorder(call_id=call_id, scenario_id=scenario_id)
    bridge = RealtimeBridge(settings=settings, scenario=scenario, recorder=recorder)

    try:
        await bridge.run(websocket)
    except WebSocketDisconnect:
        pass
    finally:
        json_path, txt_path = recorder.write(CALLS_DIR / call_id)
        logger.info("Transcript saved: %s / %s", json_path, txt_path)
