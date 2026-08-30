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
    composite_sprite_over_terrain,
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
        perks={},
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


def test_composite_sprite_over_terrain_transparent_actor_pixel_leaves_terrain_untouched():
    terrain = np.array([[[10, 20, 30, 255]]], dtype=np.uint8)
    actor = np.array([[[0, 0, 0, 0]]], dtype=np.uint8)

    out = composite_sprite_over_terrain(actor, terrain)

    assert tuple(out[0, 0]) == (10, 20, 30, 255)
    assert tuple(terrain[0, 0]) == (10, 20, 30, 255)  # inputs not mutated


def test_composite_sprite_over_terrain_opaque_actor_pixel_fully_replaces_terrain():
    terrain = np.array([[[10, 20, 30, 255]]], dtype=np.uint8)
    actor = np.array([[[200, 5, 5, 255]]], dtype=np.uint8)

    out = composite_sprite_over_terrain(actor, terrain)

    assert tuple(out[0, 0]) == (200, 5, 5, 255)


def test_composite_sprite_over_terrain_partial_alpha_blends_between_the_two():
    terrain = np.array([[[10, 20, 30, 255]]], dtype=np.uint8)
    actor = np.array([[[200, 5, 5, 128]]], dtype=np.uint8)

    out = composite_sprite_over_terrain(actor, terrain)

    r, g, b, a = out[0, 0]
    assert a == 255
    assert 10 < r < 200  # strictly between the two source colors
    assert 5 < g < 20
    assert 5 < b < 30


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


def test_build_sprite_codepoints_registers_a_composite_for_every_actor_tile_kind_pair():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=4, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={
            "rat": SpriteRef(sheet="test", col=0, row=0),
            "villager": SpriteRef(sheet="test", col=1, row=0),
        },
        items={"healing_potion": SpriteRef(sheet="test", col=2, row=0)},
        tile_kinds={"floor": SpriteRef(sheet="test", col=3, row=0)},
    )
    sheet_images = {
        "test": _solid_sheet(
            [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (128, 128, 128, 255)], 16, 4,
        )
    }

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    # Base pass unchanged: entities (sorted), then items, then tile_kinds -
    # exactly PUA_START, PUA_START+1, ... - this is what the existing
    # codepoint-determinism tests/callers already rely on.
    assert result.entities["rat"] == PUA_START
    assert result.entities["villager"] == PUA_START + 1
    assert result.items["healing_potion"] == PUA_START + 2
    assert result.tile_kinds["floor"] == PUA_START + 3

    # Composite pass: one entry per (entity, tile_kind) then per (item, tile_kind),
    # appended strictly after the base pass's 4 codepoints.
    assert set(result.entities_on_tile) == {("rat", "floor"), ("villager", "floor")}
    assert set(result.items_on_tile) == {("healing_potion", "floor")}
    assert all(cp >= PUA_START + 4 for cp in result.entities_on_tile.values())
    assert all(cp >= PUA_START + 4 for cp in result.items_on_tile.values())


def test_build_sprite_codepoints_composite_codepoint_holds_the_blended_pixels():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=2, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", col=0, row=0)},
        items={},
        tile_kinds={"floor": SpriteRef(sheet="test", col=1, row=0)},
    )
    # Both fully opaque, so the composite should equal the actor's own color
    # everywhere (opaque-over-terrain fully replaces, per
    # composite_sprite_over_terrain's own contract).
    sheet_images = {"test": _solid_sheet([(200, 5, 5, 255), (10, 20, 30, 255)], 16, 2)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    composite_tile = tileset.get_tile(result.entities_on_tile[("rat", "floor")])
    assert tuple(composite_tile[0, 0]) == (200, 5, 5, 255)


def test_build_sprite_codepoints_no_composite_for_an_unmapped_tile_kind():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=1, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", col=0, row=0)},
        items={},
        tile_kinds={},  # nothing mapped - e.g. "mountain" left out deliberately
    )
    sheet_images = {"test": _solid_sheet([(255, 0, 0, 255)], 16, 1)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    assert result.entities_on_tile == {}
    assert "rat" in result.entities  # the plain sprite still registers


def test_build_sprite_codepoints_registers_a_decoration_codepoint():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=1, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={}, items={}, tile_kinds={},
        decorations={"table": SpriteRef(sheet="test", col=0, row=0)},
    )
    sheet_images = {"test": _solid_sheet([(200, 150, 100, 255)], 16, 1)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    assert "table" in result.decorations
    tile = tileset.get_tile(result.decorations["table"])
    assert tuple(tile[0, 0]) == (200, 150, 100, 255)


def test_build_sprite_codepoints_registers_a_composite_for_every_decoration_tile_kind_pair():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=3, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={}, items={},
        tile_kinds={
            "floor": SpriteRef(sheet="test", col=0, row=0),
            "plains": SpriteRef(sheet="test", col=1, row=0),
        },
        decorations={"table": SpriteRef(sheet="test", col=2, row=0)},
    )
    sheet_images = {
        "test": _solid_sheet(
            [(10, 20, 30, 255), (40, 50, 60, 255), (200, 5, 5, 255)], 16, 3,
        )
    }

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    assert set(result.decorations_on_tile) == {("table", "floor"), ("table", "plains")}
    composite_tile = tileset.get_tile(result.decorations_on_tile[("table", "floor")])
    assert tuple(composite_tile[0, 0]) == (200, 5, 5, 255)  # opaque decoration fully replaces terrain


def test_build_sprite_codepoints_no_decoration_composite_for_an_unmapped_tile_kind():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=1, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={}, items={}, tile_kinds={},
        decorations={"table": SpriteRef(sheet="test", col=0, row=0)},
    )
    sheet_images = {"test": _solid_sheet([(255, 0, 0, 255)], 16, 1)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    assert result.decorations_on_tile == {}
    assert "table" in result.decorations  # the plain sprite still registers


def test_build_sprite_codepoints_registers_a_codepoint_per_dungeon_entrance():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=2, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={}, items={}, tile_kinds={},
        dungeon_entrances={
            "prison_tower": SpriteRef(sheet="test", col=0, row=0),
            "millhaven": SpriteRef(sheet="test", col=1, row=0),
        },
    )
    sheet_images = {"test": _solid_sheet([(255, 0, 0, 255), (0, 255, 0, 255)], 16, 2)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    assert set(result.dungeon_entrances) == {"prison_tower", "millhaven"}


def test_build_sprite_codepoints_dungeon_entrance_codepoint_holds_its_own_pixels():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=2, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={}, items={}, tile_kinds={},
        dungeon_entrances={"prison_tower": SpriteRef(sheet="test", col=1, row=0)},
    )
    sheet_images = {"test": _solid_sheet([(1, 1, 1, 255), (200, 30, 30, 255)], 16, 2)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    tile = tileset.get_tile(result.dungeon_entrances["prison_tower"])
    assert tuple(tile[0, 0]) == (200, 30, 30, 255)  # the second (col=1) tile, not the first


def test_build_sprite_codepoints_dungeon_entrances_do_not_disturb_base_pass_determinism():
    """The new dungeon_entrances registration loop is additive, appended
    after tile_kinds and before the composite pass - existing callers'
    entities/items/tile_kinds codepoints must stay exactly where they were."""
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=1, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", col=0, row=0)},
        items={},
        tile_kinds={},
        dungeon_entrances={"prison_tower": SpriteRef(sheet="test", col=0, row=0)},
    )
    sheet_images = {"test": _solid_sheet([(1, 1, 1, 255)], 16, 1)}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    assert result.entities["rat"] == PUA_START
    assert result.dungeon_entrances["prison_tower"] == PUA_START + 1


def _half_transparent_sheet(opaque_color, tile_size=16):
    """A single tile_size x tile_size tile, opaque on the left half
    (opaque_color) and fully transparent on the right half - a minimal
    stand-in for an icon-style sprite (a tree/peak/tower on an otherwise
    transparent square)."""
    sheet = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    px = sheet.load()
    for x in range(tile_size // 2):
        for y in range(tile_size):
            px[x, y] = opaque_color
    return sheet


def test_build_sprite_codepoints_applies_backdrop_to_a_tile_kind():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=2, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={}, items={},
        tile_kinds={
            "plains": SpriteRef(sheet="test", col=1, row=0),
            "forest": SpriteRef(sheet="test", col=0, row=0, backdrop="plains"),
        },
    )
    sheet = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    icon = _half_transparent_sheet((200, 30, 30, 255))
    sheet.paste(icon, (0, 0))
    plains_tile = Image.new("RGBA", (16, 16), (30, 150, 30, 255))
    sheet.paste(plains_tile, (16, 0))
    sheet_images = {"test": sheet}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    forest_tile = tileset.get_tile(result.tile_kinds["forest"])
    assert tuple(forest_tile[0, 0]) == (200, 30, 30, 255)  # the icon's own opaque half, untouched
    assert tuple(forest_tile[0, 15]) == (30, 150, 30, 255)  # the transparent half, now backdrop-filled


def test_build_sprite_codepoints_tile_kind_without_backdrop_stays_transparent():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=1, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={}, items={},
        tile_kinds={"forest": SpriteRef(sheet="test", col=0, row=0)},  # no backdrop
    )
    sheet_images = {"test": _half_transparent_sheet((200, 30, 30, 255))}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    forest_tile = tileset.get_tile(result.tile_kinds["forest"])
    assert forest_tile[0, 15][3] == 0  # still transparent - opt-in only


def test_build_sprite_codepoints_applies_backdrop_to_a_dungeon_entrance():
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=2, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={}, items={},
        tile_kinds={"plains": SpriteRef(sheet="test", col=1, row=0)},
        dungeon_entrances={
            "prison_tower": SpriteRef(sheet="test", col=0, row=0, backdrop="plains"),
        },
    )
    sheet = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    sheet.paste(_half_transparent_sheet((90, 90, 90, 255)), (0, 0))
    sheet.paste(Image.new("RGBA", (16, 16), (30, 150, 30, 255)), (16, 0))
    sheet_images = {"test": sheet}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    entrance_tile = tileset.get_tile(result.dungeon_entrances["prison_tower"])
    assert tuple(entrance_tile[0, 15]) == (30, 150, 30, 255)


def test_build_sprite_codepoints_entity_composite_uses_the_backdrop_fixed_tile():
    """An entity standing on a backdrop-fixed tile kind should composite
    against the FIXED pixels (backdrop already baked in), not the raw
    transparent original - otherwise the entity's own transparent margins
    would still show black even after fixing the tile kind itself."""
    tileset = tcod.tileset.Tileset(16, 16)
    catalog = make_catalog()
    sheet_def = SpriteSheetDef(image="test.png", tile_size=16, columns=3, rows=1)
    manifest = SpriteManifest(
        sheets={"test": sheet_def},
        entities={"rat": SpriteRef(sheet="test", col=2, row=0)},  # fully opaque, irrelevant here
        items={},
        tile_kinds={
            "plains": SpriteRef(sheet="test", col=1, row=0),
            "forest": SpriteRef(sheet="test", col=0, row=0, backdrop="plains"),
        },
    )
    sheet = Image.new("RGBA", (48, 16), (0, 0, 0, 0))
    sheet.paste(_half_transparent_sheet((200, 30, 30, 255)), (0, 0))
    sheet.paste(Image.new("RGBA", (16, 16), (30, 150, 30, 255)), (16, 0))
    sheet.paste(_half_transparent_sheet((10, 10, 200, 255)), (32, 0))  # rat: opaque left, transparent right
    sheet_images = {"test": sheet}

    result = build_sprite_codepoints(tileset, manifest, catalog, sheet_images, {"test": None})

    composite = tileset.get_tile(result.entities_on_tile[("rat", "forest")])
    # Right half (x >= 8, i.e. column index >= 8): both the rat AND
    # forest's own icon are transparent there, so it should fall through
    # to forest's backdrop-fixed pixels (plains green), never raw black.
    # Array indexing is [row, col] = [y, x].
    assert tuple(composite[5, 10]) == (30, 150, 30, 255)


def test_apply_sprites_loads_real_files_from_disk(tmp_path):
    catalog = make_catalog()
    Image.new("RGBA", (16, 16), (9, 9, 9, 255)).save(tmp_path / "sheet.png")
    manifest = SpriteManifest(
        sheets={"test": SpriteSheetDef(image="sheet.png", tile_size=16, columns=1, rows=1)},
        entities={"rat": SpriteRef(sheet="test", col=0, row=0)},
        items={},
        tile_kinds={"floor": SpriteRef(sheet="test", col=0, row=0)},
    )
    tileset = tcod.tileset.Tileset(16, 16)

    result = apply_sprites(tileset, manifest, catalog, assets_dir=tmp_path)

    assert "rat" in result.entities
    tile = tileset.get_tile(result.entities["rat"])
    assert tuple(tile[0, 0]) == (9, 9, 9, 255)
    assert ("rat", "floor") in result.entities_on_tile
