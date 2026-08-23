"""Registers bitmap sprite tiles into a tcod Tileset at Unicode Private Use
Area codepoints (U+E000+), layered on top of the existing font-based
Tileset - see main.py's load_tileset(). engine/render.py's _resolved_glyph
is the only place these codepoints are ever looked up; every other
console.print() call (HUD/log/quest-log/shop prose) never touches a PUA
codepoint, so this module has no effect on anything but the single-glyph
map/entity rendering.

Also owns the shared-sprite recolor mechanism: several catalog entries
have no distinct art of their own and reuse one base sprite (e.g. every
Wayford NPC role reuses RLTiles' plain "human" sprite) - recolor_sprite
retints that shared sprite toward the matching EntityDef/ItemDef's own
`color` field, so each still reads as visually distinct with zero new art
authoring, now or for anything added to the catalog later.

Split for testability: recolor_sprite() and build_sprite_codepoints() are
pure functions over already-decoded PIL Images / numpy arrays - no file
I/O - so tests can exercise them with tiny synthetic in-memory
images/arrays, no real PNG fixtures needed. apply_sprites() is the thin
wrapper that actually opens files from assets_dir."""

from __future__ import annotations

import colorsys
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    import tcod.tileset

    from content.loader import Catalog, SpriteManifest
    from content.schema import Color, SpriteRef, SpriteSheetDef

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "tilesets"
PUA_START = 0xE000

# Hue/saturation band a pixel must fall in to be treated as "skin" and left
# untouched by recolor - narrow on purpose: a wider net also catches
# fully-saturated rust/orange clothing (found by testing against a real
# sprite during prototyping, where it wrongly protected an orange jacket
# from being recolored).
SKIN_HUE = 20 / 360
SKIN_HUE_TOLERANCE = 12 / 360
SKIN_SAT_MIN, SKIN_SAT_MAX = 0.25, 0.55
RECOLOR_VALUE_MIN, RECOLOR_VALUE_MAX = 0.10, 0.95


@dataclass
class SpriteCodepoints:
    """entity_id / item_id / tile-kind -> the PUA codepoint registered for
    it. A missing key (including every key, for the all-defaults case) means
    "no sprite mapped" - engine/render.py's _resolved_glyph falls back to
    the authored ASCII glyph, so this is always a safe value for a catalog
    id or tile kind nothing has been mapped for yet."""

    entities: dict[str, int] = field(default_factory=dict)
    items: dict[str, int] = field(default_factory=dict)
    tile_kinds: dict[str, int] = field(default_factory=dict)


def _is_skin_tone(h: float, s: float) -> bool:
    hue_dist = min(abs(h - SKIN_HUE), 1 - abs(h - SKIN_HUE))
    return hue_dist <= SKIN_HUE_TOLERANCE and SKIN_SAT_MIN <= s <= SKIN_SAT_MAX


def recolor_sprite(rgba: np.ndarray, target_color: "Color") -> np.ndarray:
    """Retints every non-transparent, non-skin-tone, non-near-black,
    non-near-white pixel to target_color's hue+saturation, keeping each
    pixel's own value/lightness so shading/highlights/folds survive.
    rgba is (H, W, 4) uint8; returns a new array of the same shape."""
    th, ts, _ = colorsys.rgb_to_hsv(target_color[0] / 255, target_color[1] / 255, target_color[2] / 255)

    out = rgba.copy()
    height, width, _ = rgba.shape
    for y in range(height):
        for x in range(width):
            r, g, b, a = rgba[y, x]
            if a == 0:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if not (RECOLOR_VALUE_MIN <= v <= RECOLOR_VALUE_MAX) or _is_skin_tone(h, s):
                continue
            nr, ng, nb = colorsys.hsv_to_rgb(th, ts, v)
            out[y, x, 0] = round(nr * 255)
            out[y, x, 1] = round(ng * 255)
            out[y, x, 2] = round(nb * 255)
    return out


class _SheetIndex(NamedTuple):
    names: list[str]
    width: int


def _load_sheet_image(sheet_def: "SpriteSheetDef", assets_dir: Path) -> Image.Image:
    return Image.open(assets_dir / sheet_def.image).convert("RGBA")


def _load_sheet_index(sheet_def: "SpriteSheetDef", assets_dir: Path) -> _SheetIndex | None:
    if sheet_def.index is None:
        return None
    with (assets_dir / sheet_def.index).open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return _SheetIndex(names=raw["tiles"], width=raw["width"])


def _tile_box(
    sheet_def: "SpriteSheetDef", ref: "SpriteRef", index: "_SheetIndex | None"
) -> tuple[int, int, int, int]:
    """Pixel crop box (left, top, right, bottom) for one SpriteRef against
    its sheet - raises a clear error for an unknown name or an out-of-bounds
    col/row, the bounds-checking content/loader.py's pure-YAML
    load_sprite_manifest deliberately doesn't do."""
    step = sheet_def.tile_size + sheet_def.spacing
    if ref.name is not None:
        if index is None:
            raise ValueError(f"sheet has no index to look up name '{ref.name}' in")
        if ref.name not in index.names:
            raise ValueError(f"sprite name '{ref.name}' not found in sheet index")
        i = index.names.index(ref.name)
        row, col = divmod(i, index.width)
    else:
        col, row = ref.col, ref.row
        if sheet_def.columns is not None and col >= sheet_def.columns:
            raise ValueError(f"col {col} out of bounds (sheet has {sheet_def.columns} columns)")
        if sheet_def.rows is not None and row >= sheet_def.rows:
            raise ValueError(f"row {row} out of bounds (sheet has {sheet_def.rows} rows)")
    left, top = col * step, row * step
    return (left, top, left + sheet_def.tile_size, top + sheet_def.tile_size)


def build_sprite_codepoints(
    tileset: "tcod.tileset.Tileset",
    manifest: "SpriteManifest",
    catalog: "Catalog",
    sheet_images: dict[str, Image.Image],
    sheet_indexes: dict[str, "_SheetIndex | None"],
) -> SpriteCodepoints:
    """Given already-decoded sheet images (+ already-parsed indexes), crops/
    resizes every mapped tile to tileset's own tile size, recolors it when
    ref.recolor is set (target color read straight off the matching
    EntityDef/ItemDef in catalog - no new authoring), registers it into
    `tileset` at a fresh sequential PUA codepoint, and returns the lookup
    render.py needs. Deterministic assignment order (entities, then items,
    then tile_kinds, each sorted by key) so re-running with the same
    manifest always assigns the same codepoints."""
    result = SpriteCodepoints()
    next_codepoint = PUA_START
    tile_shape = (tileset.tile_height, tileset.tile_width)

    def _register(ref: "SpriteRef", color: "Color | None") -> int:
        nonlocal next_codepoint
        sheet_def = manifest.sheets[ref.sheet]
        box = _tile_box(sheet_def, ref, sheet_indexes.get(ref.sheet))
        tile = sheet_images[ref.sheet].crop(box)
        if tile.size != (tile_shape[1], tile_shape[0]):
            tile = tile.resize((tile_shape[1], tile_shape[0]), Image.LANCZOS)
        rgba = np.asarray(tile, dtype=np.uint8)
        if ref.recolor:
            assert color is not None
            rgba = recolor_sprite(rgba, color)
        tileset[next_codepoint] = rgba
        codepoint = next_codepoint
        next_codepoint += 1
        return codepoint

    for entity_id in sorted(manifest.entities):
        result.entities[entity_id] = _register(
            manifest.entities[entity_id], catalog.entities[entity_id].color
        )
    for item_id in sorted(manifest.items):
        result.items[item_id] = _register(
            manifest.items[item_id], catalog.items[item_id].color
        )
    for kind in sorted(manifest.tile_kinds):
        result.tile_kinds[kind] = _register(manifest.tile_kinds[kind], None)

    return result


def apply_sprites(
    tileset: "tcod.tileset.Tileset",
    manifest: "SpriteManifest",
    catalog: "Catalog",
    assets_dir: Path = ASSETS_DIR,
) -> SpriteCodepoints:
    """Startup entry point: opens every sheet manifest.sheets references
    from assets_dir and delegates to build_sprite_codepoints(). Cheap -
    dozens of small sprites, milliseconds total - so no caching/pre-baking
    step is needed."""
    sheet_images = {
        name: _load_sheet_image(sd, assets_dir) for name, sd in manifest.sheets.items()
    }
    sheet_indexes = {
        name: _load_sheet_index(sd, assets_dir) for name, sd in manifest.sheets.items()
    }
    return build_sprite_codepoints(tileset, manifest, catalog, sheet_images, sheet_indexes)
