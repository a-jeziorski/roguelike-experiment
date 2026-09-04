"""Fractal value-noise terrain generation - macro-scale continuous terrain
blending (plains/forest/mountain/sea, say) for an overworld cell, rather
than a room-and-corridor dungeon layout.

Pure Python, no third-party noise library: none is in requirements.txt, and
value noise (interpolating a lattice of random values, rather than dotting
random gradients the way classic Perlin noise does) is simple enough to
implement correctly from scratch and produces the same kind of smooth,
continuous field this needs.
"""

from __future__ import annotations

import random

from tools.procgen.base import Grid

# Default terrain bands, low noise value to high: sea in the lowest basins,
# then open plains, then forest on higher ground, then mountain peaks -
# the same terrain vocabulary docs/world_history.md's Geography section
# already establishes for the Heartlands. `thresholds[i]` is the upper
# bound (exclusive) of `band_kinds[i]`; a value at or above the last
# threshold gets `band_kinds[-1]`.
DEFAULT_THRESHOLDS: list[float] = [0.3, 0.55, 0.8]
DEFAULT_BAND_KINDS: list[str] = ["sea", "plains", "forest", "mountain"]


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _lattice_value(perm: list[int], x: int, y: int) -> float:
    return perm[(perm[x & 255] + y) & 255] / 255.0


def _sample(perm: list[int], x: float, y: float) -> float:
    x0, y0 = int(x // 1), int(y // 1)
    fx, fy = x - x0, y - y0
    v00 = _lattice_value(perm, x0, y0)
    v10 = _lattice_value(perm, x0 + 1, y0)
    v01 = _lattice_value(perm, x0, y0 + 1)
    v11 = _lattice_value(perm, x0 + 1, y0 + 1)
    sx, sy = _smoothstep(fx), _smoothstep(fy)
    top = v00 + sx * (v10 - v00)
    bottom = v01 + sx * (v11 - v01)
    return top + sy * (bottom - top)


def fbm(
    perm: list[int], x: float, y: float,
    scale: float, octaves: int, persistence: float, lacunarity: float,
) -> float:
    """Fractal Brownian motion: `octaves` layers of `_sample` at doubling
    (by `lacunarity`) frequency and halving (by `persistence`) amplitude,
    summed and renormalized to [0, 1]."""
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_amplitude = 0.0
    for _ in range(octaves):
        total += _sample(perm, x * frequency / scale, y * frequency / scale) * amplitude
        max_amplitude += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return total / max_amplitude


def generate(
    seed: int,
    width: int,
    height: int,
    scale: float = 20.0,
    octaves: int = 4,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
    thresholds: list[float] | None = None,
    band_kinds: list[str] | None = None,
) -> Grid:
    """Generates a `width`x`height` Grid of terrain kinds by thresholding a
    fractal value-noise field. `scale` is the lattice spacing in tiles
    (bigger = broader, slower-changing features); `octaves`/`persistence`/
    `lacunarity` control how much fine detail layers on top of that broad
    shape. `thresholds`/`band_kinds` (see DEFAULT_THRESHOLDS/
    DEFAULT_BAND_KINDS) must satisfy `len(band_kinds) == len(thresholds) + 1`.
    """
    thresholds = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    band_kinds = DEFAULT_BAND_KINDS if band_kinds is None else band_kinds
    if len(band_kinds) != len(thresholds) + 1:
        raise ValueError("band_kinds must have exactly one more entry than thresholds")

    rng = random.Random(seed)
    perm = list(range(256))
    rng.shuffle(perm)

    grid = Grid.filled(width, height, band_kinds[0])
    for y in range(height):
        for x in range(width):
            n = fbm(perm, x, y, scale, octaves, persistence, lacunarity)
            band = len(thresholds)
            for i, t in enumerate(thresholds):
                if n < t:
                    band = i
                    break
            grid.set(x, y, band_kinds[band])
    return grid
