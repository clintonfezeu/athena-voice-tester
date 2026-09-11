"""In-memory transcript capture for a single call, plus disk persistence.

`RealtimeBridge` appends turns to a `TranscriptRecorder` as OpenAI Realtime
transcription events arrive during the live call; the orchestrator writes
the finished recorder out to `data/calls/<call_id>/` once the call ends.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Who said a given line.
SPEAKER_PATIENT_BOT = "patient_bot"  # our simulated caller (OpenAI Realtime)
SPEAKER_AGENT_UNDER_TEST = "athena_agent"  # the real system being tested


@dataclass
class Turn:
    speaker: str
    text: str
    timestamp: str


@dataclass
class TranscriptRecorder:
    call_id: str
    scenario_id: str
    turns: list[Turn] = field(default_factory=list)

    def add_turn(self, speaker: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.turns.append(Turn(speaker=speaker, text=text, timestamp=_now_iso()))

    def as_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "scenario_id": self.scenario_id,
            "turns": [asdict(t) for t in self.turns],
        }

    def as_text(self) -> str:
        lines = [f"Call: {self.call_id}  |  Scenario: {self.scenario_id}", ""]
        for t in self.turns:
            label = "PATIENT (bot)" if t.speaker == SPEAKER_PATIENT_BOT else "AGENT (Athena)"
            lines.append(f"[{t.timestamp}] {label}: {t.text}")
        return "\n".join(lines) + "\n"

    def write(self, directory: Path | str) -> tuple[Path, Path]:
        """Write `transcript.json` and `transcript.txt` into `directory`."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        json_path = directory / "transcript.json"
        json_path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

        txt_path = directory / "transcript.txt"
        txt_path.write_text(self.as_text(), encoding="utf-8")

        return json_path, txt_path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")
