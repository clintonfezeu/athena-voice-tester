"""LLM-judged bug analysis: compares a call transcript against the
scenario's expected behavior and produces structured findings.

This is deliberately a *second*, separate model call rather than something
the live Realtime session does inline — judging the whole conversation at
once, after the fact, with a plain-text model gives more reliable
structured output than trying to reason about quality mid-call, and it
keeps "have the conversation" and "judge the conversation" independently
testable and replayable.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from openai import OpenAI

from bot.config import Settings, get_settings
from bot.personas import Scenario
from bot.transcript import SPEAKER_AGENT_UNDER_TEST, SPEAKER_PATIENT_BOT

logger = logging.getLogger(__name__)

VALID_SEVERITIES = ("Low", "Medium", "High")
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "One-line bug summary."},
                    "severity": {"type": "string", "enum": list(VALID_SEVERITIES)},
                    "detail": {
                        "type": "string",
                        "description": "What happened, why it's a problem, what should have happened instead.",
                    },
                    "quoted_turn": {
                        "type": "string",
                        "description": "A short direct quote from Athena's side of the transcript showing the issue.",
                    },
                },
                "required": ["summary", "severity", "detail", "quoted_turn"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

ANALYSIS_SYSTEM_PROMPT = """\
You are a meticulous QA reviewer for a medical practice's AI phone agent, \
nicknamed "Athena". You will be given the transcript of one phone call \
between a simulated patient (the caller) and Athena (the agent being \
tested), plus the scenario's goal and the behaviors the call was designed \
to probe.

Your job is to find real, useful bugs in Athena's responses — not the \
caller's. Only flag things that would actually matter to a patient or the \
practice: wrong information, broken booking/scheduling logic, ignoring \
what the patient said, failing to check something it should have checked \
(like office hours before confirming a time), dropping part of a \
multi-part request, mishandling corrections, or unsafe handling of an \
urgent situation.

Do NOT flag:
- Minor phrasing, filler words, or disfluencies
- Anything about the caller/patient's own behavior
- Cosmetic issues that wouldn't matter to a real patient
- Speculation not actually supported by the transcript

If the call went cleanly and nothing genuinely wrong happened, return an \
empty findings list — that's a perfectly good, honest result. Quality \
over quantity: a couple of well-described real issues beat a long list \
of nitpicks.

For each finding, `quoted_turn` must be a short, verbatim quote from \
Athena's side of the transcript that shows the problem, so a human can \
find it quickly.
"""


def analyze_call(
    scenario: Scenario,
    transcript: dict,
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> list[dict]:
    """Return a list of finding dicts for one call's transcript."""
    settings = settings or get_settings()
    client = client or OpenAI(api_key=settings.openai_api_key)

    user_prompt = (
        f"Scenario: {scenario.title}\n"
        f"Patient's goal: {scenario.goal}\n\n"
        f"Success criteria:\n{_bullets(scenario.success_criteria)}\n\n"
        f"Expected agent behavior:\n{_bullets(scenario.expected_agent_behavior)}\n\n"
        f"Transcript:\n{_format_transcript(transcript)}"
    )

    response = client.chat.completions.create(
        model=settings.openai_analysis_model,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "call_findings", "schema": FINDINGS_SCHEMA, "strict": True},
        },
    )

    payload = json.loads(response.choices[0].message.content)
    findings = payload.get("findings", [])
    for finding in findings:
        if finding.get("severity") not in VALID_SEVERITIES:
            finding["severity"] = "Medium"
    return findings


def analyze_and_save(
    call_dir: Path,
    scenario: Scenario,
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> Path:
    """Load `call_dir/transcript.json`, analyze it, write `call_dir/findings.json`."""
    transcript = json.loads((call_dir / "transcript.json").read_text(encoding="utf-8"))
    findings = analyze_call(scenario, transcript, settings=settings, client=client)

    out_path = call_dir / "findings.json"
    out_path.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    logger.info("Wrote %d finding(s) -> %s", len(findings), out_path)
    return out_path


def build_bug_report(calls_dir: Path = Path("data/calls")) -> str:
    """Aggregate every `data/calls/*/findings.json` into one markdown report."""
    entries: list[tuple[str, str, dict]] = []

    for call_dir in sorted(calls_dir.glob("*")):
        findings_path = call_dir / "findings.json"
        if not findings_path.exists():
            continue
        metadata_path = call_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        for finding in json.loads(findings_path.read_text(encoding="utf-8")):
            entries.append((call_dir.name, metadata.get("scenario_id", "unknown"), finding))

    lines = ["# Bug Report", "", "Auto-aggregated from `data/calls/*/findings.json`.", ""]

    if not entries:
        lines.append("_No findings yet — run some calls, then `python -m bot.cli analyze-all`._")
        return "\n".join(lines) + "\n"

    entries.sort(key=lambda e: SEVERITY_ORDER.get(e[2].get("severity", "Medium"), 1))

    for call_id, scenario_id, finding in entries:
        lines += [
            f"## {finding.get('summary', '(no summary)')}",
            f"- **Severity:** {finding.get('severity', 'Medium')}",
            f"- **Call:** `{call_id}` (scenario: `{scenario_id}`) — "
            f"see `data/calls/{call_id}/transcript.txt`",
            f'- **Quoted:** "{finding.get("quoted_turn", "")}"',
            "",
            finding.get("detail", ""),
            "",
        ]

    return "\n".join(lines) + "\n"


def write_bug_report(
    out_path: Path = Path("reports/BUG_REPORT.md"),
    calls_dir: Path = Path("data/calls"),
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_bug_report(calls_dir), encoding="utf-8")
    return out_path


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- (none specified)"


def _format_transcript(transcript: dict) -> str:
    lines = []
    for turn in transcript.get("turns", []):
        label = "PATIENT" if turn.get("speaker") == SPEAKER_PATIENT_BOT else "ATHENA"
        if turn.get("speaker") not in (SPEAKER_PATIENT_BOT, SPEAKER_AGENT_UNDER_TEST):
            label = turn.get("speaker", "UNKNOWN").upper()
        lines.append(f"{label}: {turn.get('text', '')}")
    return "\n".join(lines)
