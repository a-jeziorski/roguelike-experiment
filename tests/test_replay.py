"""Tests for tools/replay.py's pure, non-windowed pieces - load_frames and
clamp_index. The actual windowed present/event loop stays untested, same as
main.py's own run_trainer_mode/run_shop_mode etc. today."""

import json

import pytest

from tools.replay import clamp_index, load_frames


def _write_jsonl(path, frames):
    path.write_text("\n".join(json.dumps(f) for f in frames) + "\n", encoding="utf-8")


def test_load_frames_reads_lines_in_order(tmp_path):
    path = tmp_path / "session.jsonl"
    _write_jsonl(path, [{"argv": ["new"]}, {"argv": ["wait"]}, {"argv": ["wait"]}])

    frames = load_frames(path)

    assert [f["argv"] for f in frames] == [["new"], ["wait"], ["wait"]]


def test_load_frames_skips_blank_lines(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_text('{"argv": ["new"]}\n\n{"argv": ["wait"]}\n', encoding="utf-8")

    frames = load_frames(path)

    assert len(frames) == 2


def test_load_frames_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_frames(tmp_path / "does_not_exist.jsonl")


def test_load_frames_empty_file_raises_value_error(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError):
        load_frames(path)


def test_clamp_index_next_within_range():
    assert clamp_index(2, 1, 10) == 3


def test_clamp_index_next_clamps_at_last():
    assert clamp_index(9, 1, 10) == 9


def test_clamp_index_prev_within_range():
    assert clamp_index(2, -1, 10) == 1


def test_clamp_index_prev_clamps_at_first():
    assert clamp_index(0, -1, 10) == 0


def test_clamp_index_jump_to_first():
    assert clamp_index(5, -100, 10) == 0


def test_clamp_index_jump_to_last():
    assert clamp_index(5, 100, 10) == 9
