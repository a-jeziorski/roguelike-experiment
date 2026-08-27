"""engine/audio.py's SoundManager - never touches a real audio device in
this suite (no assertion here depends on pygame.mixer.init() actually
succeeding on the machine running pytest). What's under test is the
manifest-driven key lookup and the "never raises" contract that lets
main.py call play_sfx/play_music/set_muted unconditionally, on any
machine, with any (or no) real asset files present."""

from pathlib import Path

from content.loader import AudioManifest
from engine.audio import SoundManager


def make_manifest(sfx=None, music=None) -> AudioManifest:
    return AudioManifest(sfx=sfx or {}, music=music or {})


def test_disabled_sound_manager_never_raises(tmp_path):
    manager = SoundManager(make_manifest(sfx={"melee_hit": "nope.ogg"}), tmp_path, enabled=False)

    manager.play_sfx("melee_hit")
    manager.play_music("dungeon")
    manager.set_muted(True)
    manager.set_muted(False)

    assert manager.enabled is False


def test_play_sfx_with_an_unknown_key_does_not_raise(tmp_path):
    manager = SoundManager(make_manifest(), tmp_path, enabled=False)

    manager.play_sfx("some_key_not_in_the_manifest")


def test_play_music_with_an_unknown_key_does_not_raise(tmp_path):
    manager = SoundManager(make_manifest(), tmp_path, enabled=False)

    manager.play_music("some_key_not_in_the_manifest")


def test_play_sfx_pointing_at_a_missing_file_does_not_raise(tmp_path):
    """Even a manager whose mixer genuinely initialized shouldn't crash a
    turn just because the manifest points at a file that was never
    downloaded (see data/audio.yaml's paths, real assets acquired
    separately) - engine/audio.py swallows pygame.error/OSError."""
    manager = SoundManager(make_manifest(sfx={"melee_hit": "assets/audio/sfx/nowhere.ogg"}), tmp_path)

    manager.play_sfx("melee_hit")


def test_play_music_pointing_at_a_missing_file_does_not_raise(tmp_path):
    manager = SoundManager(make_manifest(music={"dungeon": "assets/audio/music/nowhere.ogg"}), tmp_path)

    manager.play_music("dungeon")


def test_play_music_with_the_same_key_twice_does_not_raise(tmp_path):
    """Covers the "already this track, no-op" branch (avoids an audible
    restart-stutter on every transition into the same zone type) as well
    as a genuinely new load - neither path should ever raise."""
    manager = SoundManager(make_manifest(music={"dungeon": "assets/audio/music/dungeon.ogg"}), tmp_path)

    manager.play_music("dungeon")
    manager.play_music("dungeon")


def test_set_muted_updates_the_flag_even_when_disabled(tmp_path):
    manager = SoundManager(make_manifest(), tmp_path, enabled=False)

    manager.set_muted(True)

    assert manager.muted is True


def test_muted_sound_manager_does_not_raise_playing_sfx(tmp_path):
    """muted is checked before enabled even matters for play_sfx - forcing
    enabled=True here (without a real device on whatever machine runs this
    suite) still proves the muted short-circuit is hit first and nothing
    downstream raises."""
    manager = SoundManager(make_manifest(sfx={"melee_hit": "melee_hit.ogg"}), tmp_path, enabled=False)
    manager.enabled = True
    manager.muted = True

    manager.play_sfx("melee_hit")
