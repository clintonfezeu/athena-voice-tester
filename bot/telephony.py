"""Twilio REST helpers: place the outbound call, poll it, fetch its recording.

`bot.server` handles the *live* side of a call (TwiML + the media-stream
websocket); this module handles the *control* side — asking Twilio to dial
out in the first place, and pulling the finished call's recording down
once it's over.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
from twilio.rest import Client

from bot.config import Settings

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "busy", "failed", "no-answer", "canceled"}


def build_client(settings: Settings) -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def place_call(client: Client, settings: Settings, scenario_id: str, call_id: str):
    """Dial `settings.target_number`, pointing Twilio's webhook at our `/twiml`.

    Recording is enabled (dual-channel, so each side of the conversation
    stays on its own audio channel) from the moment the call connects.
    """
    twiml_url = f"{settings.twiml_url}?scenario_id={scenario_id}&call_id={call_id}"
    call = client.calls.create(
        to=settings.target_number,
        from_=settings.twilio_from_number,
        url=twiml_url,
        record=True,
        recording_channels="dual",
        timeout=30,
    )
    logger.info("Placed call sid=%s (scenario=%s call_id=%s)", call.sid, scenario_id, call_id)
    return call


def wait_for_call_completion(
    client: Client,
    call_sid: str,
    max_wait_seconds: int,
    poll_interval: float = 3.0,
):
    """Poll the call resource until it reaches a terminal status, or time out."""
    deadline = time.monotonic() + max_wait_seconds
    call = client.calls(call_sid).fetch()

    while call.status not in TERMINAL_STATUSES and time.monotonic() < deadline:
        time.sleep(poll_interval)
        call = client.calls(call_sid).fetch()

    if call.status not in TERMINAL_STATUSES:
        logger.warning(
            "Call %s did not reach a terminal status within %ss (last status=%s)",
            call_sid,
            max_wait_seconds,
            call.status,
        )
    return call


def fetch_recording(client: Client, settings: Settings, call_sid: str, out_dir: Path) -> Path | None:
    """Download the call's recording as an mp3 into `out_dir`. Returns the path, or None."""
    recordings = client.calls(call_sid).recordings.list(limit=1)
    if not recordings:
        logger.warning("No recording found for call %s", call_sid)
        return None

    recording = recordings[0]
    media_url = f"https://api.twilio.com{recording.uri.rsplit('.', 1)[0]}.mp3"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "recording.mp3"

    with httpx.Client(auth=(settings.twilio_account_sid, settings.twilio_auth_token)) as http_client:
        resp = http_client.get(media_url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)

    logger.info("Saved recording for call %s -> %s", call_sid, out_path)
    return out_path
