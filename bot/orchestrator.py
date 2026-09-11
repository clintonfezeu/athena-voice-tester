"""End-to-end call orchestration: dial a scenario, wait, save the artifacts.

Requires `bot.server:app` to already be running and publicly reachable at
`PUBLIC_BASE_URL` (e.g. via `uvicorn` + `ngrok`) — this module only drives
Twilio's REST API to place/poll the call and pull down the recording; the
live audio bridge and transcript capture happen inside the server process.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bot.config import Settings, get_settings
from bot.personas import Scenario, load_all_scenarios
from bot.telephony import build_client, fetch_recording, place_call, wait_for_call_completion

logger = logging.getLogger(__name__)

CALLS_DIR = Path("data/calls")

# Extra time (beyond the scenario's own safety cap) to allow for dialing,
# ringing, and Twilio's own webhook round-trips before we give up polling.
POLL_GRACE_SECONDS = 60


@dataclass
class CallResult:
    call_id: str
    scenario_id: str
    call_sid: str | None
    status: str
    duration_seconds: int | None
    recording_path: str | None
    transcript_path: str | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status == "completed"


def run_call(scenario: Scenario, settings: Settings | None = None) -> CallResult:
    """Place one call for `scenario`, wait for it to finish, save artifacts."""
    settings = settings or get_settings()
    call_id = f"{scenario.id}-{uuid4().hex[:8]}"
    call_dir = CALLS_DIR / call_id
    client = build_client(settings)

    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        call = place_call(client, settings, scenario.id, call_id)
        call = wait_for_call_completion(
            client,
            call.sid,
            max_wait_seconds=settings.max_call_duration_seconds + POLL_GRACE_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - one bad call shouldn't kill a batch
        logger.exception("Call failed for scenario=%s", scenario.id)
        return CallResult(
            call_id=call_id,
            scenario_id=scenario.id,
            call_sid=None,
            status="error",
            duration_seconds=None,
            recording_path=None,
            transcript_path=None,
            error=str(exc),
        )

    recording_path = None
    try:
        path = fetch_recording(client, settings, call.sid, call_dir)
        recording_path = str(path) if path else None
    except Exception:  # noqa: BLE001
        logger.exception("Failed to fetch recording for call_sid=%s", call.sid)

    transcript_path = str(call_dir / "transcript.json") if (call_dir / "transcript.json").exists() else None

    metadata = {
        "call_id": call_id,
        "scenario_id": scenario.id,
        "call_sid": call.sid,
        "status": call.status,
        "to": settings.target_number,
        "from": settings.twilio_from_number,
        "started_at": started_at,
        "duration_seconds": int(call.duration) if call.duration else None,
    }
    call_dir.mkdir(parents=True, exist_ok=True)
    (call_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return CallResult(
        call_id=call_id,
        scenario_id=scenario.id,
        call_sid=call.sid,
        status=call.status,
        duration_seconds=metadata["duration_seconds"],
        recording_path=recording_path,
        transcript_path=transcript_path,
    )


def run_batch(
    scenarios: list[Scenario] | None = None,
    settings: Settings | None = None,
    delay_seconds: int | None = None,
) -> list[CallResult]:
    """Run every scenario (or a given subset), pacing calls with a delay between them."""
    settings = settings or get_settings()
    scenarios = scenarios if scenarios is not None else load_all_scenarios()
    delay = settings.batch_call_delay_seconds if delay_seconds is None else delay_seconds

    results: list[CallResult] = []
    for i, scenario in enumerate(scenarios):
        logger.info("Running scenario %d/%d: %s", i + 1, len(scenarios), scenario.id)
        results.append(run_call(scenario, settings=settings))

        if i < len(scenarios) - 1 and delay > 0:
            time.sleep(delay)

    return results


def results_summary(results: list[CallResult]) -> str:
    lines = ["Call batch summary", "=" * 19]
    for r in results:
        marker = "OK  " if r.ok else "FAIL"
        detail = r.error or r.status
        lines.append(f"[{marker}] {r.scenario_id:<40} call_id={r.call_id} ({detail})")
    ok_count = sum(1 for r in results if r.ok)
    lines.append("")
    lines.append(f"{ok_count}/{len(results)} calls completed successfully")
    return "\n".join(lines)


def result_to_dict(result: CallResult) -> dict:
    return asdict(result)
