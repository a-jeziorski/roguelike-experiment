"""Exercises the sprite pipeline (recolor + PUA codepoint registration)
without any real PNG/JSON asset files - build_sprite_codepoints() takes
already-decoded images/indexes, so tests build tiny synthetic ones in
memory. Only test_apply_sprites_loads_real_files_from_disk touches the
filesystem."""

import numpy as np
import pytest
import tcod.tileset
from PIL import Image

from content.loader import Catalog, SpriteManifest
from content.schema import EntityDef, ItemDef, SpriteRef, SpriteSheetDef
from engine.sprites import (
    PUA_START,
    SpriteCodepoints,
    _SheetIndex,
    apply_sprites,
    build_sprite_codepoints,
    recolor_sprite,
)


def make_catalog() -> Catalog:
    return Catalog(
        entities={
            "villager": EntityDef(
                id="villager", name="Villager", glyph="v", color=(170, 140, 90),
                hp=5, attack=0, defense=0, ai="villager",
            ),
            "rat": EntityDef(
                id="rat", name="Rat", glyph="r", color=(140, 90, 60),
                hp=5, attack=2, defense=0, ai="skittish",
            ),
        },
        items={
            "healing_potion": ItemDef(
                id="healing_potion", name="Healing Potion", glyph="!", color=(220, 40, 100),
            ),
        },
    )


def test_recolor_sprite_leaves_transparent_pixels_untouched():
    rgba = np.zeros((1, 4, 4), dtype=np.uint8)
    rgba[0, 0] = (10, 20, 30, 0)  # fully transparent
    out = recolor_sprite(rgba, target_color=(200, 30, 30))
    assert tuple(out[0, 0]) == (10, 20, 30, 0)


def test_recolor_sprite_leaves_skin_tone_pixels_untouched():
    # hue ~20deg, sat ~0.4, a real skin-tone pixel sampled from the
    # prototyped "human" RLTiles sprite.
    skin = (202, 143, 114, 255)
    rgba = np.array([[skin]], dtype=np.uint8)
    out = recolor_sprite(rgba, target_color=(30, 30, 200))
    assert tuple(out[0, 0]) == skin


def test_recolor_sprite_leaves_near_black_outline_pixels_untouched():
    black = (5, 5, 5, 255)
    rgba = np.array([[black]], dtype=np.uint8)
    out = recolor_sprite(rgba, target_color=(30, 30, 200))
    assert tuple(out[0, 0]) == black


def test_recolor_sprite_retints_a_plain_pixel_toward_the_target_hue():
    import colorsys

    gray = (128, 128, 128, 255)
    rgba = np.array([[gray]], dtype=np.uint8)
    target = (30, 144, 30)  # a saturated green

    out = recolor_sprite(rgba, target_color=target)

    r, g, b, a = out[0, 0]
    assert a == 255
    out_h, out_s, out_v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    target_h, target_s, _ = colorsys.rgb_to_hsv(target[0] / 255, target[1] / 255, target[2] / 255)
    _, _, original_v = colorsys.rgb_to_hsv(128 / 255, 128 / 255, 128 / 255)
    assert out_h == pytest.approx(target_h, abs=0.01)
    assert out_s == pytest.approx(target_s, abs=0.01)
    assert out_v == pytest.approx(original_v, abs=0.01)  # lightness/shading preserved


def _solid_sheet(colors: list[tuple[int, int, int, int]], tile_size: int, columns: int) -> Image.Image:
    """A synthetic sheet image: `len(colors)` tiles of tile_size x tile_size,
    each a flat color, laid out left-to-right/top-to-bottom in a `columns`-
    wide grid with no spacing - enough to exercise crop/resize/registration
    without a real asset file."""
    rows = (len(colors) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * tile_size, rows * tile_size))
    for i, color in enumerate(colors):
        row, col = divmod(i, columns)
        tile = Image.new("RGBA", (tile_size, tile_size), color)
        sheet.paste(tile, (col * tile_size, row * tile_size))
    return sheet


def test_build_sprite_codepoints_assigns_deterministic_sequential_codepoints():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=2, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={
            "villager": SpriteRef(sheet="test", col=0, row=0),
            "rat": SpriteRef(sheet="test", col=1, row=0),
        },
        items={"healing_potion": SpriteRef(sheet="test", col=0, row=0)},
        tile_kinds={},
    )
    sheet_images = {"test": _solid_sheet([(255, 0, 0, 255), (0, 255, 0, 255)], 16, 2)}
    sheet_indexes = {"test": None}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, sheet_indexes)

    # entities (sorted: "rat", "villager"), then items ("healing_potion").
    assert result.entities["rat"] == PUA_START
    assert result.entities["villager"] == PUA_START + 1
    assert result.items["healing_potion"] == PUA_START + 2


def test_build_sprite_codepoints_registers_the_correct_cropped_pixels():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=2, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", col=1, row=0)},
        items={},
        tile_kinds={},
    )
    sheet_images = {"test": _solid_sheet([(255, 0, 0, 255), (0, 255, 0, 255)], 16, 2)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    tile = tileset.get_tile(result.entities["rat"])
    assert tuple(tile[0, 0]) == (0, 255, 0, 255)  # the second (col=1) tile, not the first


def test_build_sprite_codepoints_resizes_a_sprite_to_the_tileset_tile_size():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=32, columns=1, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", col=0, row=0)},
        items={}, tile_kinds={},
    )
    sheet_images = {"test": _solid_sheet([(10, 20, 30, 255)], 32, 1)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    tile = tileset.get_tile(result.entities["rat"])
    assert tile.shape == (16, 16, 4)


def test_build_sprite_codepoints_recolors_only_when_ref_recolor_is_true():
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=1, rows=1)
    gray = (128, 128, 128, 255)
    sheet_images = {"test": _solid_sheet([gray], 16, 1)}

    plain_tileset = tcod.tileset.Tileset(16, 16)
    plain_result = build_sprite_codepoints(
        plain_tileset,
        SpriteManifest(
            sheets={"test": sheet_def},
            entities={"villager": SpriteRef(sheet="test", col=0, row=0, recolor=False)},
            items={}, tile_kinds={},
        ),
        catalog, sheet_images, {"test": None},
    )
    recolored_tileset = tcod.tileset.Tileset(16, 16)
    recolored_result = build_sprite_codepoints(
        recolored_tileset,
        SpriteManifest(
            sheets={"test": sheet_def},
            entities={"villager": SpriteRef(sheet="test", col=0, row=0, recolor=True)},
            items={}, tile_kinds={},
        ),
        catalog, sheet_images, {"test": None},
    )

    plain_tile = plain_tileset.get_tile(plain_result.entities["villager"])
    recolored_tile = recolored_tileset.get_tile(recolored_result.entities["villager"])
    assert tuple(plain_tile[0, 0]) == gray
    assert tuple(recolored_tile[0, 0][:3]) != gray[:3]


def test_build_sprite_codepoints_addresses_by_name_via_the_sheet_index():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, index="test.json")
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", name="rat_sprite")},
        items={}, tile_kinds={},
    )
    sheet_images = {"test": _solid_sheet([(1, 1, 1, 255), (2, 2, 2, 255)], 16, 2)}
    sheet_indexes = {"test": _SheetIndex(names=["other_sprite", "rat_sprite"], width=2)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, sheet_indexes)

    tile = tileset.get_tile(result.entities["rat"])
    assert tuple(tile[0, 0]) == (2, 2, 2, 255)  # index 1 -> row 0, col 1


def test_build_sprite_codepoints_raises_for_an_unknown_name():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, index="test.json")
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", name="nonexistent")},
        items={}, tile_kinds={},
    )
    sheet_images = {"test": _solid_sheet([(1, 1, 1, 255)], 16, 1)}
    sheet_indexes = {"test": _SheetIndex(names=["rat_sprite"], width=1)}

    with pytest.raises(ValueError, match="not found in sheet index"):
        build_sprite_codepoints(tileset, manifest, catalog, sheet_images, sheet_indexes)


def test_build_sprite_codepoints_raises_for_an_out_of_bounds_column():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=2, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", col=5, row=0)},
        items={}, tile_kinds={},
    )
    sheet_images = {"test": _solid_sheet([(1, 1, 1, 255), (2, 2, 2, 255)], 16, 2)}

    with pytest.raises(ValueError, match="out of bounds"):
        build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})


def test_apply_sprites_loads_real_files_from_disk(tmp_path):
    catalog = make_catalog()
    Image.new("RGBA", (16, 16), (9, 9, 9, 255)).save(tmp_path / "sheet.png")
    manifest = SpriteManifest(
        sheets={"test": SpriteSheetDef(image="sheet.png", tile_size=16, columns=1, rows=1)},
        entities={"rat": SpriteRef(sheet="test", col=0, row=0)},
        items={}, tile_kinds={},
    )
    tileset = tcod.tileset.Tileset(16, 16)

    result = apply_sprites(tileset, manifest, catalog, assets_dir=tmp_path)

    assert "rat" in result.entities
    tile = tileset.get_tile(result.entities["rat"])
    assert tuple(tile[0, 0]) == (9, 9, 9, 255)
