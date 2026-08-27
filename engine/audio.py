"""Sound playback, driven entirely from main.py's SDL event loop - never
imported by Engine or anything else under pytest's headless coverage.
See Engine.sound_events (engine/engine.py) for how game logic signals
what to play without knowing anything about pygame.

Every method on SoundManager is safe to call even if the audio device
never initialized (no hardware, headless CI, or the real asset files
just haven't been downloaded yet) - sound is a pure bonus here, never a
requirement for a turn to resolve.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from content.loader import AudioManifest

_SILENT_ERRORS = (pygame.error, OSError)


class SoundManager:
    def __init__(self, manifest: AudioManifest, base_dir: Path, enabled: bool = True):
        self.manifest = manifest
        self.base_dir = base_dir
        self.muted = False
        self._current_music_key: str | None = None
        self.enabled = enabled and self._init_mixer()

    def _init_mixer(self) -> bool:
        try:
            pygame.mixer.init()
        except _SILENT_ERRORS:
            return False
        return True

    def play_sfx(self, key: str) -> None:
        if not self.enabled or self.muted:
            return
        relative = self.manifest.sfx.get(key)
        if relative is None:
            return
        try:
            pygame.mixer.Sound(str(self.base_dir / relative)).play()
        except _SILENT_ERRORS:
            pass

    def play_music(self, key: str) -> None:
        """No-ops if `key` is already the track playing - avoids an audible
        restart-stutter on every transition into the same zone type (e.g.
        two dungeon levels visited back to back)."""
        if not self.enabled or key == self._current_music_key:
            return
        relative = self.manifest.music.get(key)
        if relative is None:
            return
        try:
            pygame.mixer.music.load(str(self.base_dir / relative))
            pygame.mixer.music.set_volume(0.0 if self.muted else 1.0)
            pygame.mixer.music.play(loops=-1)
        except _SILENT_ERRORS:
            return
        self._current_music_key = key

    def set_muted(self, muted: bool) -> None:
        self.muted = muted
        if self.enabled:
            try:
                pygame.mixer.music.set_volume(0.0 if muted else 1.0)
            except _SILENT_ERRORS:
                pass
