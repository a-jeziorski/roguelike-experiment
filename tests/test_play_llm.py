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


def test_walk_records_one_frame_per_step_plus_a_summary_frame(tmp_path):
    """A multi-step walk/goto used to record only one frame for the whole
    command, so a replay jumped straight from the start position to the
    end position instead of showing the route actually walked. Each
    executed step now gets its own frame via _execute_walk's on_step hook,
    on top of the existing end-of-command summary frame."""
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])
    main(["--save", str(save_path), "--record", str(record_path), "walk", "s", "s", "e"])

    frames = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]
    walk_frames = [f for f in frames if f["argv"][0] == "walk"]
    assert len(walk_frames) == 4  # 3 step frames + 1 summary frame
    assert [f["notes"] for f in walk_frames[:3]] == [["Step 1/3"], ["Step 2/3"], ["Step 3/3"]]
    assert "Completed all requested steps." in walk_frames[3]["notes"]


def test_walk_step_frames_show_the_actual_route_not_a_teleport(tmp_path):
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])
    main(["--save", str(save_path), "--record", str(record_path), "walk", "s", "s", "e"])

    frames = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]
    positions = [(f["save"]["player"]["x"], f["save"]["player"]["y"]) for f in frames]
    # (2, 2) is The Solitary Cell's own starting position - each step
    # frame shows one more tile of progress, not the start and end alone.
    assert positions == [(2, 2), (2, 3), (2, 4), (3, 4), (3, 4)]


def test_walk_across_a_level_transition_reports_the_new_level_separately(tmp_path):
    """Regression test for the goto/walk coordinate-blending bug: when a
    multi-step move crosses into a different level partway through, the
    reported end position used to be printed as a continuation of the old
    level's own coordinates ("(a, b) -> (c, d)"), even though (c, d) is
    only meaningful in the new level's coordinate space. It should now be
    reported as a separate arrival instead."""
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])
    # (2, 2) -> east x3 reaches (5, 2), directly below The Solitary Cell's
    # own up-stairs at (5, 1) - the 4th step (north) walks onto them and
    # leads out to the overworld, all within this one call.
    main(["--save", str(save_path), "--record", str(record_path), "walk", "e", "e", "e", "n"])

    frames = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]
    summary = frames[-1]
    assert summary["argv"] == ["walk", "e", "e", "e", "n"]
    assert not any("->" in note for note in summary["notes"])
    assert any(note.startswith("Walked 4/4 step(s) from (2, 2).") for note in summary["notes"])
    assert any(note.startswith("Entered The Sundered Realm at ") for note in summary["notes"])
    assert summary["save"]["places"]["overworld"] is not None


def test_goto_across_a_level_transition_reports_the_new_level_separately(tmp_path):
    """Same bug, reached via goto's own pathfinding instead of a literal
    walk sequence - the real way this surfaced during a playtest session
    (goto-ing toward an overworld coordinate that happened to path onto a
    dungeon entrance)."""
    save_path = tmp_path / "save.json"
    record_path = tmp_path / "session.jsonl"

    main(["--save", str(save_path), "--record", str(record_path), "new"])
    main(["--save", str(save_path), "--record", str(record_path), "goto", "5", "1"])

    frames = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]
    summary = frames[-1]
    assert summary["argv"] == ["goto", "5", "1"]
    walked_notes = [n for n in summary["notes"] if n.startswith("Walked")]
    assert walked_notes and "->" not in walked_notes[0]
    assert any(note.startswith("Entered The Sundered Realm at ") for note in summary["notes"])
