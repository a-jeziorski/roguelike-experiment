"""Tests for tools/play_llm.py's --record option (see tools/replay.py for the
viewer). Each test drives main() directly against tmp_path files, the same
pattern tests/test_save.py already uses for save-file round-trips."""

import json

from engine.save import SaveGame
from tools.play_llm import main


def test_record_writes_one_frame_per_mutating_command(tmp_path):
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])
    main(["--save", str(save_path), "--record", str(record_path), "wait"])

    lines = record_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_record_frame_has_the_expected_shape(tmp_path):
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])

    frame = json.loads(record_path.read_text(encoding="utf-8").splitlines()[0])
    assert frame["argv"] == ["new"]
    assert isinstance(frame["notes"], list)
    assert isinstance(frame["messages"], list)
    assert "save" in frame
    # The embedded save payload round-trips through the real SaveGame model -
    # same serialization save_to_path already uses, not a parallel format.
    SaveGame.model_validate(frame["save"])


def test_record_frame_captures_this_steps_own_messages(tmp_path):
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])

    frame = json.loads(record_path.read_text(encoding="utf-8").splitlines()[0])
    assert any("enter" in m["text"] for m in frame["messages"])
    for m in frame["messages"]:
        assert set(m) == {"text", "category", "speaker"}


def test_record_appends_in_order_across_calls(tmp_path):
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])
    main(["--save", str(save_path), "--record", str(record_path), "wait"])
    main(["--save", str(save_path), "--record", str(record_path), "wait"])

    frames = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]
    assert [f["argv"] for f in frames] == [["new"], ["wait"], ["wait"]]


def test_query_command_does_not_write_a_frame(tmp_path):
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])
    main(["--save", str(save_path), "--record", str(record_path), "character"])

    lines = record_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1  # only "new" - "character" never mutates/persists


def test_no_record_flag_creates_no_file(tmp_path):
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "new"])

    assert not record_path.exists()
