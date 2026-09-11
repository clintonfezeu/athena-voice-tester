import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bot.bug_analyzer import analyze_and_save, analyze_call, build_bug_report, write_bug_report
from bot.personas import get_scenario
from bot.transcript import SPEAKER_AGENT_UNDER_TEST, SPEAKER_PATIENT_BOT, TranscriptRecorder


def _mock_openai_client(findings: list[dict]):
    client = MagicMock()
    message = MagicMock()
    message.content = json.dumps({"findings": findings})
    choice = MagicMock(message=message)
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client


def _sample_transcript() -> dict:
    rec = TranscriptRecorder(call_id="c1", scenario_id="edge_weekend_request_out_of_hours")
    rec.add_turn(speaker=SPEAKER_PATIENT_BOT, text="Can I come in this Sunday at 10am?")
    rec.add_turn(speaker=SPEAKER_AGENT_UNDER_TEST, text="I've scheduled you for Sunday at 10am.")
    return rec.as_dict()


def test_analyze_call_returns_findings_from_model(settings_env):
    scenario = get_scenario("edge_weekend_request_out_of_hours")
    client = _mock_openai_client([
        {
            "summary": "Booked a Sunday appointment despite the office being closed",
            "severity": "High",
            "detail": "Agent confirmed Sunday 10am without checking hours.",
            "quoted_turn": "I've scheduled you for Sunday at 10am.",
        }
    ])

    findings = analyze_call(scenario, _sample_transcript(), client=client)

    assert len(findings) == 1
    assert findings[0]["severity"] == "High"
    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"]
    assert "Sunday" in kwargs["messages"][1]["content"]


def test_analyze_call_normalizes_invalid_severity(settings_env):
    scenario = get_scenario("edge_weekend_request_out_of_hours")
    client = _mock_openai_client([
        {"summary": "x", "severity": "Critical!!", "detail": "y", "quoted_turn": "z"}
    ])

    findings = analyze_call(scenario, _sample_transcript(), client=client)
    assert findings[0]["severity"] == "Medium"


def test_analyze_call_can_return_no_findings(settings_env):
    scenario = get_scenario("simple_scheduling_new_patient")
    client = _mock_openai_client([])
    findings = analyze_call(scenario, _sample_transcript(), client=client)
    assert findings == []


def test_analyze_and_save_writes_findings_json(settings_env, tmp_path):
    scenario = get_scenario("edge_weekend_request_out_of_hours")
    call_dir = tmp_path / "call-1"
    call_dir.mkdir()
    (call_dir / "transcript.json").write_text(json.dumps(_sample_transcript()), encoding="utf-8")

    client = _mock_openai_client([{"summary": "s", "severity": "Low", "detail": "d", "quoted_turn": "q"}])
    from bot.config import get_settings

    out_path = analyze_and_save(call_dir, scenario, settings=get_settings(), client=client)

    assert out_path == call_dir / "findings.json"
    saved = json.loads(out_path.read_text(encoding="utf-8"))
    assert saved[0]["summary"] == "s"


@pytest.fixture
def calls_dir_with_findings(tmp_path):
    call_a = tmp_path / "call-a"
    call_a.mkdir()
    (call_a / "metadata.json").write_text(json.dumps({"scenario_id": "s1"}), encoding="utf-8")
    (call_a / "findings.json").write_text(json.dumps([
        {"summary": "Low severity thing", "severity": "Low", "detail": "d1", "quoted_turn": "q1"},
        {"summary": "High severity thing", "severity": "High", "detail": "d2", "quoted_turn": "q2"},
    ]), encoding="utf-8")

    call_b = tmp_path / "call-b"
    call_b.mkdir()
    (call_b / "findings.json").write_text(json.dumps([]), encoding="utf-8")

    return tmp_path


def test_build_bug_report_orders_by_severity(calls_dir_with_findings):
    report = build_bug_report(calls_dir_with_findings)
    assert report.index("High severity thing") < report.index("Low severity thing")
    assert "call-a" in report


def test_build_bug_report_empty_state():
    report = build_bug_report(calls_dir=Path("/nonexistent-dir-xyz"))
    assert "No findings yet" in report


def test_write_bug_report_creates_file(calls_dir_with_findings, tmp_path):
    out_path = tmp_path / "reports" / "BUG_REPORT.md"
    result = write_bug_report(out_path=out_path, calls_dir=calls_dir_with_findings)
    assert result.exists()
    assert "High severity thing" in result.read_text(encoding="utf-8")
