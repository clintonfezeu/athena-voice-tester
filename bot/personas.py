"""Loads and validates patient-persona test scenarios from YAML.

Each scenario describes a "patient" character and a goal for the call
(e.g. "book a first-time cleaning appointment"). The realtime voice bridge
turns a scenario into a system prompt for the OpenAI Realtime session that
plays the caller; the bug analyzer uses the same scenario's
``expected_agent_behavior``/``success_criteria`` to judge the transcript.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"

REQUIRED_FIELDS = ("id", "title", "category", "persona", "goal", "opening_line")


class ScenarioError(ValueError):
    """Raised when a scenario file is missing or malformed."""


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    category: str
    persona: str
    goal: str
    opening_line: str
    talking_points: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    expected_agent_behavior: list[str] = field(default_factory=list)
    max_turns: int = 20
    source_path: Path | None = None

    @property
    def system_prompt(self) -> str:
        """Prompt handed to the OpenAI Realtime session to play this patient."""
        points = "\n".join(f"- {p}" for p in self.talking_points) or "- (nothing specific)"
        return (
            "You are a patient calling a medical practice's phone line. "
            "You are NOT an assistant and must never break character or "
            f"mention you are an AI or a test. Stay fully in character as: "
            f"{self.persona}\n\n"
            f"Your goal for this call: {self.goal}\n\n"
            f"Things you may bring up if it comes up naturally:\n{points}\n\n"
            "Rules for how you talk:\n"
            "- Speak naturally, like a real person on the phone: short "
            "sentences, the occasional filler word, realistic pacing and "
            "pauses.\n"
            "- Say one thing at a time, then stop and actually listen to "
            "the agent's reply before continuing — do not monologue.\n"
            "- Stay focused on your goal, but react naturally if the agent "
            "asks a clarifying or unexpected question.\n"
            f'- Open the call with something like: "{self.opening_line}"\n'
            "- Once your goal is resolved, refused, or clearly a dead end, "
            "thank the agent and end the call naturally — don't drag it "
            "out."
        )


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ScenarioError(f"{path}: scenario file must be a YAML mapping")
    return data


def load_scenario(path: Path | str) -> Scenario:
    """Load and validate a single scenario YAML file."""
    path = Path(path)
    data = _load_yaml(path)

    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise ScenarioError(f"{path}: missing required field(s): {', '.join(missing)}")

    return Scenario(
        id=data["id"],
        title=data["title"],
        category=data["category"],
        persona=data["persona"],
        goal=data["goal"],
        opening_line=data["opening_line"],
        talking_points=list(data.get("talking_points", []) or []),
        success_criteria=list(data.get("success_criteria", []) or []),
        expected_agent_behavior=list(data.get("expected_agent_behavior", []) or []),
        max_turns=int(data.get("max_turns", 20)),
        source_path=path,
    )


def load_all_scenarios(directory: Path | str = SCENARIOS_DIR) -> list[Scenario]:
    """Load every scenario in a directory, sorted by filename."""
    directory = Path(directory)
    files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
    scenarios = [load_scenario(f) for f in files]

    ids = [s.id for s in scenarios]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ScenarioError(f"Duplicate scenario id(s) in {directory}: {sorted(duplicates)}")

    return scenarios


def get_scenario(scenario_id: str, directory: Path | str = SCENARIOS_DIR) -> Scenario:
    """Look up a single scenario by its ``id`` field."""
    for scenario in load_all_scenarios(directory):
        if scenario.id == scenario_id:
            return scenario
    raise ScenarioError(f"No scenario with id={scenario_id!r} found in {directory}")
