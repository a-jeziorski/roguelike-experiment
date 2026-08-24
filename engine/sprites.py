"""Registers bitmap sprite tiles into a tcod Tileset at Unicode Private Use
Area codepoints (U+E000+), layered on top of the existing font-based
Tileset - see main.py's load_tileset(). engine/render.py's _resolved_glyph
(tile kinds) and _resolved_entity_glyph (entities/items) are the only
places these codepoints are ever looked up; every other console.print()
call (HUD/log/quest-log/shop prose) never touches a PUA codepoint, so this
module has no effect on anything but the single-glyph map/entity rendering.

Also owns the shared-sprite recolor mechanism: several catalog entries
have no distinct art of their own and reuse one base sprite (e.g. every
Wayford NPC role reuses RLTiles' plain "human" sprite) - recolor_sprite
retints that shared sprite toward the matching EntityDef/ItemDef's own
`color` field, so each still reads as visually distinct with zero new art
authoring, now or for anything added to the catalog later.

And the entity/item-over-terrain compositing mechanism
(composite_sprite_over_terrain): a Console cell holds exactly one glyph,
so drawing an entity's sprite over a tile fully replaces the tile's own
codepoint rather than blending with it - wherever the entity's sprite is
transparent, the console's plain background shows through instead of the
terrain that should be visible there. build_sprite_codepoints
precomputes every (entity/item, tile_kind) composite once at startup so
render.py never needs live Tileset access during play.

The same problem also hits an icon-style tile_kinds/dungeon_entrances
sprite directly (a single tree/peak/tower silhouette on an otherwise
transparent square, unlike a full-bleed texture like plains/sea/wall) -
there's no "what's it standing on" question to answer dynamically for a
tile kind, so SpriteRef.backdrop names another tile_kinds entry to
composite it over once, at registration time, baked permanently into the
same codepoint - no new fallback logic, no render.py change needed.

Split for testability: recolor_sprite(), composite_sprite_over_terrain(),
and build_sprite_codepoints() are pure functions over already-decoded PIL
Images / numpy arrays - no file I/O - so tests can exercise them with tiny
synthetic in-memory images/arrays, no real PNG fixtures needed.
apply_sprites() is the thin wrapper that actually opens files from
assets_dir."""

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
    id or tile kind nothing has been mapped for yet.

    entities_on_tile/items_on_tile hold a second kind of codepoint: an
    actor's sprite pre-composited over a specific tile kind's own sprite
    (see composite_sprite_over_terrain), keyed by (actor_id, tile_kind) -
    used whenever both the actor and the tile kind it's standing on have a
    sprite mapped, so the actor's transparent background shows the real
    terrain instead of a plain black square. Missing a (actor_id, tile_kind)
    pair - e.g. the tile kind has no sprite mapped at all - falls back to
    the actor's plain codepoint above; see engine/render.py's
    _resolved_entity_glyph for the full fallback chain.

    dungeon_entrances holds a third kind: a dungeon registry id -> the
    codepoint for that specific dungeon's own overworld entrance icon (a
    house for a town, a tower for a keep) - a complete standalone tile
    image, never composited over anything, same as tile_kinds. A dungeon
    id missing here falls back to tile_kinds' generic dungeon_entrance
    sprite, then to ASCII - see engine/render.py's _resolved_tile_glyph."""

    entities: dict[str, int] = field(default_factory=dict)
    items: dict[str, int] = field(default_factory=dict)
    tile_kinds: dict[str, int] = field(default_factory=dict)
    entities_on_tile: dict[tuple[str, str], int] = field(default_factory=dict)
    items_on_tile: dict[tuple[str, str], int] = field(default_factory=dict)
    dungeon_entrances: dict[str, int] = field(default_factory=dict)


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


def composite_sprite_over_terrain(actor_rgba: np.ndarray, terrain_rgba: np.ndarray) -> np.ndarray:
    """Alpha-composites an already-recolored/resized entity or item sprite
    over a tile-kind's own sprite, using the actor's own per-pixel alpha as
    the blend mask (standard "over" compositing): a fully transparent
    actor pixel leaves the terrain pixel untouched, a fully opaque one
    fully replaces it, and any partial alpha blends proportionally. Both
    arrays must already be the same (H, W, 4) uint8 shape - guaranteed by
    build_sprite_codepoints, which resizes every sprite to the tileset's
    own tile_shape before this is ever called. Returns a new array; neither
    input is mutated."""
    base = Image.fromarray(terrain_rgba, mode="RGBA")
    top = Image.fromarray(actor_rgba, mode="RGBA")
    return np.asarray(Image.alpha_composite(base, top), dtype=np.uint8)


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
    then tile_kinds, then dungeon_entrances, each sorted by key) so
    re-running with the same manifest always assigns the same codepoints.
    dungeon_entrances is registered the same way as tile_kinds (no color/
    recolor, a complete standalone tile image) - it's keyed by dungeon id
    rather than tile kind, but is otherwise just another base-pass entry.

    A second pass then registers every (entity/item, tile_kind) composite
    (see composite_sprite_over_terrain) for every actor and tile kind that
    both have a sprite mapped - eagerly, once, here at startup rather than
    lazily during play, since the full set is small and bounded
    ((entities + items) x tile_kinds - a few hundred tiny composites at
    most) and this keeps engine/render.py free of any live Tileset access.
    This pass is strictly appended after the base one above, so the base
    codepoints stay exactly where existing callers already expect them."""
    result = SpriteCodepoints()
    next_codepoint = PUA_START
    tile_shape = (tileset.tile_height, tileset.tile_width)

    def _register(ref: "SpriteRef", color: "Color | None") -> tuple[int, np.ndarray]:
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
        return codepoint, rgba

    entity_pixels: dict[str, np.ndarray] = {}
    item_pixels: dict[str, np.ndarray] = {}
    tile_pixels: dict[str, np.ndarray] = {}

    for entity_id in sorted(manifest.entities):
        # The player isn't a real catalog entry (see
        # content.loader.PLAYER_ENTITY_ID) - it has no .color to recolor
        # toward, which load_sprite_manifest already enforces by rejecting
        # recolor: true on it, so None here is never actually used.
        edef = catalog.entities.get(entity_id)
        codepoint, rgba = _register(
            manifest.entities[entity_id], edef.color if edef is not None else None
        )
        result.entities[entity_id] = codepoint
        entity_pixels[entity_id] = rgba
    for item_id in sorted(manifest.items):
        codepoint, rgba = _register(manifest.items[item_id], catalog.items[item_id].color)
        result.items[item_id] = codepoint
        item_pixels[item_id] = rgba
    for kind in sorted(manifest.tile_kinds):
        codepoint, rgba = _register(manifest.tile_kinds[kind], None)
        result.tile_kinds[kind] = codepoint
        tile_pixels[kind] = rgba
    dungeon_entrance_pixels: dict[str, np.ndarray] = {}
    for dungeon_id in sorted(manifest.dungeon_entrances):
        codepoint, rgba = _register(manifest.dungeon_entrances[dungeon_id], None)
        result.dungeon_entrances[dungeon_id] = codepoint
        dungeon_entrance_pixels[dungeon_id] = rgba

    # Backdrop pass: an icon-style tile_kinds/dungeon_entrances sprite (a
    # single tree/peak/tower silhouette, unlike a full-bleed texture like
    # plains/sea/wall) has its own transparent background composited over
    # its declared backdrop tile, once, here - baked into the SAME
    # already-registered codepoint (no new codepoint, no render.py change
    # needed). Runs before the entity/item composite pass below so an
    # entity standing on a backdrop-fixed tile kind (e.g. stairs_down)
    # composites against the fixed version, not the raw transparent one.
    for kind in sorted(manifest.tile_kinds):
        backdrop = manifest.tile_kinds[kind].backdrop
        if backdrop is None:
            continue
        fixed = composite_sprite_over_terrain(tile_pixels[kind], tile_pixels[backdrop])
        tileset[result.tile_kinds[kind]] = fixed
        tile_pixels[kind] = fixed
    for dungeon_id in sorted(manifest.dungeon_entrances):
        backdrop = manifest.dungeon_entrances[dungeon_id].backdrop
        if backdrop is None:
            continue
        fixed = composite_sprite_over_terrain(dungeon_entrance_pixels[dungeon_id], tile_pixels[backdrop])
        tileset[result.dungeon_entrances[dungeon_id]] = fixed

    for entity_id in sorted(entity_pixels):
        for kind in sorted(tile_pixels):
            composite = composite_sprite_over_terrain(entity_pixels[entity_id], tile_pixels[kind])
            tileset[next_codepoint] = composite
            result.entities_on_tile[(entity_id, kind)] = next_codepoint
            next_codepoint += 1
    for item_id in sorted(item_pixels):
        for kind in sorted(tile_pixels):
            composite = composite_sprite_over_terrain(item_pixels[item_id], tile_pixels[kind])
            tileset[next_codepoint] = composite
            result.items_on_tile[(item_id, kind)] = next_codepoint
            next_codepoint += 1

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
