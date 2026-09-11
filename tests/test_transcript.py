import json

from bot.transcript import SPEAKER_AGENT_UNDER_TEST, SPEAKER_PATIENT_BOT, TranscriptRecorder


def test_add_turn_records_speaker_and_text():
    rec = TranscriptRecorder(call_id="c1", scenario_id="s1")
    rec.add_turn(speaker=SPEAKER_PATIENT_BOT, text="Hi, I'd like to book an appointment.")
    rec.add_turn(speaker=SPEAKER_AGENT_UNDER_TEST, text="Sure, what day works for you?")

    assert len(rec.turns) == 2
    assert rec.turns[0].speaker == SPEAKER_PATIENT_BOT
    assert rec.turns[1].speaker == SPEAKER_AGENT_UNDER_TEST


def test_add_turn_ignores_blank_text():
    rec = TranscriptRecorder(call_id="c1", scenario_id="s1")
    rec.add_turn(speaker=SPEAKER_PATIENT_BOT, text="   ")
    rec.add_turn(speaker=SPEAKER_PATIENT_BOT, text="")
    assert rec.turns == []


def test_as_dict_roundtrips_through_json():
    rec = TranscriptRecorder(call_id="c1", scenario_id="s1")
    rec.add_turn(speaker=SPEAKER_PATIENT_BOT, text="hello")
    data = json.loads(json.dumps(rec.as_dict()))
    assert data["call_id"] == "c1"
    assert data["scenario_id"] == "s1"
    assert data["turns"][0]["text"] == "hello"


def test_as_text_labels_each_speaker():
    rec = TranscriptRecorder(call_id="c1", scenario_id="s1")
    rec.add_turn(speaker=SPEAKER_PATIENT_BOT, text="hello there")
    rec.add_turn(speaker=SPEAKER_AGENT_UNDER_TEST, text="hi, how can I help")
    text = rec.as_text()
    assert "PATIENT (bot)" in text
    assert "AGENT (Athena)" in text
    assert "hello there" in text


def test_write_creates_json_and_txt_files(tmp_path):
    rec = TranscriptRecorder(call_id="c1", scenario_id="s1")
    rec.add_turn(speaker=SPEAKER_PATIENT_BOT, text="hello")

    out_dir = tmp_path / "call-1"
    json_path, txt_path = rec.write(out_dir)

    assert json_path.exists()
    assert txt_path.exists()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["call_id"] == "c1"
    assert "hello" in txt_path.read_text(encoding="utf-8")
