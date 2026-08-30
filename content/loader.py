"""Loads and validates hand-authored content files.

This is the safety net for the whole "content is hand-edited" workflow: anything
a human (or Claude) can get wrong in a .lvl or catalog file should be caught here,
with a clear message, before the engine ever sees it.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

import yaml
from pydantic import ValidationError

from content.schema import (
    PEACEFUL_AI_TYPES,
    TILE_PASSABILITY,
    AudioManifestDef,
    CellsManifestDef,
    DecorationKind,
    DungeonDef,
    EncounterDef,
    EntityDef,
    FlagDialogue,
    ItemDef,
    LevelDef,
    PerkDef,
    QuestDef,
    SpriteManifestDef,
    SpriteRef,
    SpriteSheetDef,
    TileType,
)

# Every TileType except player_start actually appears in a runtime GameMap -
# build_game_map always rewrites a player_start cell to that level's
# player_start_tile (see engine/game_map.py), so player_start itself never
# exists as a live kind for a sprite to apply to. This is the valid key set
# for sprites.yaml's tile_kinds section.
_VALID_SPRITE_TILE_KINDS = set(get_args(TileType)) - {"player_start"}

# The valid key set for sprites.yaml's decorations section - see
# content/schema.py's DecorationKind.
_VALID_DECORATION_KINDS = set(get_args(DecorationKind))

# The player Entity's entity_id (see engine/game_map.py's build_game_map) -
# reserved rather than a real catalog entry, since the player is hardcoded
# outside entities.yaml. load_sprite_manifest allows this one id under
# sprites.yaml's entities section even though it never appears in
# Catalog.entities, so a sprite can still be authored for it.
PLAYER_ENTITY_ID = "player"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ContentValidationError(Exception):
    """Raised when a content file fails validation. Collects every problem found
    rather than stopping at the first, since fixing hand-edited files one error
    at a time is tedious."""

    def __init__(self, source: str, errors: list[str]):
        self.source = source
        self.errors = errors
        message = f"Invalid content in {source}:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        super().__init__(message)


@dataclass
class Catalog:
    entities: dict[str, EntityDef]
    items: dict[str, ItemDef]
    perks: dict[str, PerkDef]


@dataclass
class EntitySpawn:
    x: int
    y: int
    entity: EntityDef
    dialogue: str | None = None
    flag_dialogue: list[FlagDialogue] = field(default_factory=list)
    elite: bool = False


@dataclass
class ItemSpawn:
    x: int
    y: int
    item: ItemDef


@dataclass
class DecorationSpawn:
    x: int
    y: int
    kind: str  # a DecorationKind value - already validated by LegendEntry's pydantic type


@dataclass
class StairsSpawn:
    x: int
    y: int
    # None = terminal stairway - reaching it leaves the dungeon and returns to
    # the overworld (either kind can now be terminal: a stairs_down terminal
    # is a dungeon's usual "completed it" exit, a stairs_up terminal is a
    # retreat point near the entrance).
    next_level: str | None
    kind: Literal["stairs_down", "stairs_up"]


@dataclass
class DoorSpawn:
    x: int
    y: int
    requires_key: str  # id of the key item that unlocks this door


@dataclass
class DungeonEntranceSpawn:
    x: int
    y: int
    dungeon_id: str  # overworld-only: a dungeon registry id, not a level id


@dataclass
class TileDescriptionSpawn:
    x: int
    y: int
    text: str  # overrides the tile kind's generic look-mode description
    announce: bool = False  # auto-log text to the message log on first FOV entry
    # Whether the underlying legend entry's tile kind is "landmark" - lets
    # Engine._log_newly_seen_tile_announcements award discovery XP only for
    # a genuine point of interest, not every announce:true tile (a
    # flavorful gate/stairs/item keeps its message but grants no XP).
    is_landmark: bool = False


@dataclass
class TileSpriteSpawn:
    x: int
    y: int
    sprite_id: str  # a data/sprites.yaml tile_sprite_overrides key - see LegendEntry.tile_sprite


@dataclass
class ParsedLevel:
    """A validated level, decoupled from any engine/rendering data structures.
    tiles[y][x] gives the TileType string for that cell. A level may have multiple
    stairways (branching), each with its own destination. dungeon_entrances is
    only ever populated for the overworld (see load_overworld) - every dungeon
    level leaves it empty."""

    id: str
    name: str
    width: int
    height: int
    tiles: list[list[str]]
    player_start: tuple[int, int]
    player_start_tile: str
    entity_spawns: list[EntitySpawn]
    item_spawns: list[ItemSpawn]
    stairs: list[StairsSpawn]
    doors: list[DoorSpawn]
    dungeon_entrances: list[DungeonEntranceSpawn]
    tile_descriptions: list[TileDescriptionSpawn]
    open_boundary: bool
    open_boundary_message: str
    dark: bool
    # Purely cosmetic map dressing (see DecorationKind) - defaulted so every
    # other ParsedLevel construction site (overworld cells, which don't
    # author decorations today) keeps working unchanged.
    decoration_spawns: list[DecorationSpawn] = field(default_factory=list)
    # Per-coordinate sprite overrides (see LegendEntry.tile_sprite) -
    # defaulted for the same reason as decoration_spawns above.
    tile_sprite_spawns: list[TileSpriteSpawn] = field(default_factory=list)


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_catalog(
    entities_path: Path = DATA_DIR / "entities.yaml",
    items_path: Path = DATA_DIR / "items.yaml",
    perks_path: Path = DATA_DIR / "perks.yaml",
) -> Catalog:
    entities: dict[str, EntityDef] = {}
    errors: list[str] = []

    raw_entities = _load_yaml(entities_path) or {}
    for entity_id, raw in raw_entities.items():
        try:
            entities[entity_id] = EntityDef(id=entity_id, **raw)
        except ValidationError as e:
            errors.append(f"entity '{entity_id}': {e}")

    items: dict[str, ItemDef] = {}
    raw_items = _load_yaml(items_path) or {}
    for item_id, raw in raw_items.items():
        try:
            items[item_id] = ItemDef(id=item_id, **raw)
        except ValidationError as e:
            errors.append(f"item '{item_id}': {e}")

    perks: dict[str, PerkDef] = {}
    raw_perks = _load_yaml(perks_path) or {}
    for perk_id, raw in raw_perks.items():
        try:
            perks[perk_id] = PerkDef(id=perk_id, **raw)
        except ValidationError as e:
            errors.append(f"perk '{perk_id}': {e}")

    for perk_id, pdef in perks.items():
        if pdef.requires_perk_id is None:
            continue
        if pdef.requires_perk_id not in perks:
            errors.append(f"perk '{perk_id}': requires_perk_id references unknown perk '{pdef.requires_perk_id}'")
        elif pdef.requires_perk_id == perk_id:
            errors.append(f"perk '{perk_id}': requires_perk_id can't reference itself")

    # A cycle in the requires_perk_id chain (A requires B requires A) would
    # make every perk in it permanently unlearnable - each one waiting on
    # the next, forever. Walk each perk's own chain of prerequisites;
    # revisiting a perk already seen on this walk means a cycle. Skipped
    # once a chain runs into an unknown id - already reported above, and
    # `current in perks` naturally stops the walk there instead of raising.
    for perk_id, pdef in perks.items():
        seen = {perk_id}
        current = pdef.requires_perk_id
        while current is not None and current in perks:
            if current in seen:
                errors.append(f"perk '{perk_id}': requires_perk_id chain forms a cycle through '{current}'")
                break
            seen.add(current)
            current = perks[current].requires_perk_id

    for entity_id, edef in entities.items():
        if not edef.shop_inventory:
            continue
        if edef.ai not in PEACEFUL_AI_TYPES:
            errors.append(
                f"entity '{entity_id}': shop_inventory is set but ai is "
                f"'{edef.ai}' - only a peaceful NPC (villager/town_guard) is "
                "ever reachable as a shopkeeper (see PEACEFUL_AI_TYPES), so "
                "this entity's stock could never be sold"
            )
        for item_id in edef.shop_inventory:
            if item_id not in items:
                errors.append(f"entity '{entity_id}': shop_inventory references unknown item '{item_id}'")
            elif items[item_id].cost is None:
                errors.append(
                    f"entity '{entity_id}': shop_inventory item '{item_id}' has "
                    "no cost set - Engine.shop_price treats a missing cost as "
                    "0, so it would sell for free"
                )

    for entity_id, edef in entities.items():
        if edef.xp_reward and edef.ai in PEACEFUL_AI_TYPES:
            errors.append(
                f"entity '{entity_id}': xp_reward is set but ai is "
                f"'{edef.ai}' - a peaceful NPC is never a legitimate kill "
                "target, so this would let the player farm XP by killing "
                "villagers/town guards"
            )
        if edef.drop_item_id is not None:
            if edef.ai in PEACEFUL_AI_TYPES:
                errors.append(
                    f"entity '{entity_id}': drop_item_id is set but ai is "
                    f"'{edef.ai}' - same reasoning as xp_reward above, a "
                    "peaceful NPC shouldn't reward the player for killing it"
                )
            if edef.drop_item_id not in items:
                errors.append(f"entity '{entity_id}': drop_item_id references unknown item '{edef.drop_item_id}'")
        if not edef.trainer_perks:
            continue
        if edef.ai not in PEACEFUL_AI_TYPES:
            errors.append(
                f"entity '{entity_id}': trainer_perks is set but ai is "
                f"'{edef.ai}' - only a peaceful NPC (villager/town_guard) is "
                "ever reachable as a trainer (see PEACEFUL_AI_TYPES), so "
                "this entity could never teach anything"
            )
        for perk_id in edef.trainer_perks:
            if perk_id not in perks:
                errors.append(f"entity '{entity_id}': trainer_perks references unknown perk '{perk_id}'")

    if errors:
        raise ContentValidationError(
            f"{entities_path.name} / {items_path.name} / {perks_path.name}", errors
        )

    return Catalog(entities=entities, items=items, perks=perks)


def load_quests(
    path: Path, catalog: Catalog, known_dungeon_ids: set[str] | None = None,
) -> dict[str, QuestDef]:
    """Loads and validates data/quests.yaml (see content/schema.py's
    QuestDef). `known_dungeon_ids` cross-checks target_dungeon_id the same
    way load_overworld checks dungeon_entrance - pass None to skip (e.g. a
    test not loading the full dungeon registry)."""
    raw = _load_yaml(path) or {}
    quests: dict[str, QuestDef] = {}
    errors: list[str] = []

    for quest_id, fields in raw.items():
        try:
            quest = QuestDef(id=quest_id, **fields)
        except ValidationError as e:
            errors.append(f"quest '{quest_id}': {e}")
            continue

        for label, entity_id in (
            ("questgiver_entity_id", quest.questgiver_entity_id),
            ("target_entity_id", quest.target_entity_id),
            ("target_kill_entity_id", quest.target_kill_entity_id),
            ("reward_shop_discount_entity_id", quest.reward_shop_discount_entity_id),
            ("target_intimidate_entity_id", quest.target_intimidate_entity_id),
            ("target_cull_entity_id", quest.target_cull_entity_id),
            ("target_preserve_entity_id", quest.target_preserve_entity_id),
        ):
            if entity_id is not None and entity_id not in catalog.entities:
                errors.append(f"quest '{quest_id}': {label} references unknown entity '{entity_id}'")

        if (
            quest.target_intimidate_entity_id is not None
            and quest.target_intimidate_entity_id in catalog.entities
            and catalog.entities[quest.target_intimidate_entity_id].ai not in PEACEFUL_AI_TYPES
        ):
            errors.append(
                f"quest '{quest_id}': target_intimidate_entity_id "
                f"'{quest.target_intimidate_entity_id}' isn't a peaceful entity - "
                "engine/combat.py only ever records an intimidation against a "
                "peaceful defender (see PEACEFUL_AI_TYPES), so a hostile target "
                "could never complete this quest"
            )

        if (
            quest.reward_shop_discount_entity_id is not None
            and quest.reward_shop_discount_entity_id in catalog.entities
            and not catalog.entities[quest.reward_shop_discount_entity_id].shop_inventory
        ):
            errors.append(
                f"quest '{quest_id}': reward_shop_discount_entity_id "
                f"'{quest.reward_shop_discount_entity_id}' has no shop_inventory - "
                "it isn't reachable as a shopkeeper (see EntityDef.shop_inventory/"
                "Engine.adjacent_shopkeeper), so this discount could never apply to anything"
            )

        for label, item_id in (
            ("target_item_id", quest.target_item_id),
            ("reward_item_id", quest.reward_item_id),
        ):
            if item_id is not None and item_id not in catalog.items:
                errors.append(f"quest '{quest_id}': {label} references unknown item '{item_id}'")

        if quest.target_dungeon_id is not None and known_dungeon_ids is not None:
            if quest.target_dungeon_id not in known_dungeon_ids:
                errors.append(
                    f"quest '{quest_id}': target_dungeon_id references unknown "
                    f"dungeon '{quest.target_dungeon_id}'"
                )

        if (
            quest.voided_by_dungeon_id is not None
            and known_dungeon_ids is not None
            and quest.voided_by_dungeon_id not in known_dungeon_ids
        ):
            errors.append(
                f"quest '{quest_id}': voided_by_dungeon_id references unknown "
                f"dungeon '{quest.voided_by_dungeon_id}'"
            )

        for consequence in quest.on_fail:
            if (
                consequence.destroy_dungeon_id is not None
                and known_dungeon_ids is not None
                and consequence.destroy_dungeon_id not in known_dungeon_ids
            ):
                errors.append(
                    f"quest '{quest_id}': on_fail destroy_dungeon_id references "
                    f"unknown dungeon '{consequence.destroy_dungeon_id}'"
                )

            if consequence.tighten_deadline is not None:
                target_id = consequence.tighten_deadline.quest_id
                if target_id == quest_id:
                    errors.append(
                        f"quest '{quest_id}': on_fail tighten_deadline can't target itself"
                    )
                elif target_id not in raw:
                    errors.append(
                        f"quest '{quest_id}': on_fail tighten_deadline references "
                        f"unknown quest '{target_id}'"
                    )
                elif raw[target_id].get("deadline_year") is None:
                    errors.append(
                        f"quest '{quest_id}': on_fail tighten_deadline targets quest "
                        f"'{target_id}', which has no deadline_year set - there's "
                        "nothing to shorten"
                    )

        if quest.on_fail and quest.deadline_year is None:
            errors.append(
                f"quest '{quest_id}': on_fail is set but there's no deadline - "
                "QuestLog.check_deadlines is the only trigger for it, so this "
                "quest could never fire any of its consequences"
            )

        if quest.target_item_id is not None and quest.questgiver_entity_id is None:
            errors.append(
                f"quest '{quest_id}': target_item_id (a fetch/delivery quest) "
                "requires questgiver_entity_id too - QuestLog.check_delivery "
                "only ever completes a fetch quest by talking to its "
                "questgiver, so one without a questgiver can never complete"
            )

        if quest.target_kill_entity_id is not None and quest.questgiver_entity_id is None:
            errors.append(
                f"quest '{quest_id}': target_kill_entity_id (a kill quest) "
                "requires questgiver_entity_id too - QuestLog.check_kill_report "
                "only ever completes a kill quest by talking to its "
                "questgiver, so one without a questgiver can never complete"
            )

        if quest.target_dungeon_id is not None and quest.questgiver_entity_id is None:
            errors.append(
                f"quest '{quest_id}': target_dungeon_id (a dungeon-arrival "
                "quest) requires questgiver_entity_id too - "
                "QuestLog.check_dungeon_report only ever completes a "
                "dungeon-arrival quest by talking to its questgiver, so one "
                "without a questgiver can never complete"
            )

        if quest.target_intimidate_entity_id is not None and quest.questgiver_entity_id is None:
            errors.append(
                f"quest '{quest_id}': target_intimidate_entity_id (an "
                "intimidate quest) requires questgiver_entity_id too - "
                "QuestLog.check_intimidate_report only ever completes an "
                "intimidate quest by talking to its questgiver, so one "
                "without a questgiver can never complete"
            )

        if quest.target_cull_entity_id is not None and quest.questgiver_entity_id is None:
            errors.append(
                f"quest '{quest_id}': target_cull_entity_id (a cull quest) "
                "requires questgiver_entity_id too - QuestLog.check_cull_report "
                "only ever completes a cull quest by talking to its "
                "questgiver, so one without a questgiver can never complete"
            )

        if quest.requires_quest_id is not None and quest.requires_quest_id not in raw:
            errors.append(
                f"quest '{quest_id}': requires_quest_id references unknown "
                f"quest '{quest.requires_quest_id}'"
            )

        if quest.requires_quest_id == quest_id:
            errors.append(f"quest '{quest_id}': requires_quest_id can't reference itself")

        if quest.questgiver_entity_id is None and quest.starting_status == "not_given":
            errors.append(
                f"quest '{quest_id}': starting_status is 'not_given' but no "
                "questgiver_entity_id is set - QuestLog.check_questgiver is "
                "the only way a not_given quest is ever granted, so this "
                "quest could never start"
            )

        quests[quest_id] = quest

    if errors:
        raise ContentValidationError(str(path), errors)

    return quests


def load_encounters(
    path: Path, known_dungeon_ids: set[str], known_quest_ids: set[str],
) -> dict[str, EncounterDef]:
    """Loads and validates data/encounters.yaml (see content/schema.py's
    EncounterDef). No catalog parameter - unlike QuestDef/EntityDef,
    EncounterDef has no entity/item references to cross-check, only dungeon
    and quest ids. Unlike load_quests' known_dungeon_ids, both cross-checks
    here are required rather than optional - an encounter with a bad
    trigger_dungeon_id/encounter_dungeon_id/gate_quest_id can never actually
    fire, which is worth catching unconditionally rather than only when a
    caller happens to pass the full registries."""
    raw = _load_yaml(path) or {}
    encounters: dict[str, EncounterDef] = {}
    errors: list[str] = []

    for encounter_id, fields in raw.items():
        try:
            encounter = EncounterDef(id=encounter_id, **fields)
        except ValidationError as e:
            errors.append(f"encounter '{encounter_id}': {e}")
            continue

        for label, dungeon_id in (
            ("trigger_dungeon_id", encounter.trigger_dungeon_id),
            ("encounter_dungeon_id", encounter.encounter_dungeon_id),
        ):
            if dungeon_id not in known_dungeon_ids:
                errors.append(
                    f"encounter '{encounter_id}': {label} references unknown "
                    f"dungeon '{dungeon_id}'"
                )

        if encounter.gate_quest_id not in known_quest_ids:
            errors.append(
                f"encounter '{encounter_id}': gate_quest_id references unknown "
                f"quest '{encounter.gate_quest_id}'"
            )

        encounters[encounter_id] = encounter

    if errors:
        raise ContentValidationError(str(path), errors)

    return encounters


@dataclass
class SpriteManifest:
    sheets: dict[str, SpriteSheetDef]
    entities: dict[str, SpriteRef]
    items: dict[str, SpriteRef]
    tile_kinds: dict[str, SpriteRef]
    dungeon_entrances: dict[str, SpriteRef] = field(default_factory=dict)
    decorations: dict[str, SpriteRef] = field(default_factory=dict)
    tile_sprite_overrides: dict[str, SpriteRef] = field(default_factory=dict)


def load_sprite_manifest(
    path: Path, catalog: Catalog, known_dungeon_ids: set[str] | None = None,
) -> SpriteManifest:
    """Loads and validates data/sprites.yaml (see content/schema.py's
    SpriteManifestDef/SpriteRef/SpriteSheetDef). Stays pure-YAML validation
    like every other load_* here - no image/pixel decoding happens in this
    module; actual pixel-bounds checking happens in engine/sprites.py, the
    layer that opens the binary sheet file anyway. Any catalog id, tile
    kind, or dungeon id with no entry in the returned manifest simply has
    no sprite - engine/render.py falls back accordingly, so an empty
    manifest (or one missing entries) is always valid, never an error.

    `known_dungeon_ids` cross-checks dungeon_entrances the same way
    load_quests checks target_dungeon_id - pass None to skip (e.g. a test
    not loading the full dungeon registry)."""
    raw = _load_yaml(path) or {}
    try:
        parsed = SpriteManifestDef(**raw)
    except ValidationError as e:
        raise ContentValidationError(str(path), [str(e)]) from e

    errors: list[str] = []

    def _check_sheet(section: str, key: str, ref: SpriteRef) -> None:
        if ref.sheet not in parsed.sheets:
            errors.append(f"{section}['{key}']: unknown sheet '{ref.sheet}'")
        elif ref.name is not None and parsed.sheets[ref.sheet].index is None:
            errors.append(
                f"{section}['{key}']: addresses by 'name' but sheet "
                f"'{ref.sheet}' has no 'index' - only a sheet with a name "
                "index can be addressed this way, use col/row instead"
            )

    def _check_backdrop(section: str, key: str, ref: SpriteRef) -> None:
        if ref.backdrop is None:
            return
        if ref.backdrop not in parsed.tile_kinds:
            errors.append(
                f"{section}['{key}']: backdrop '{ref.backdrop}' is not a "
                "tile_kinds entry - backdrop always references tile_kinds, "
                "the canonical set of full-bleed ground textures to "
                "composite an icon-style sprite over"
            )
        elif parsed.tile_kinds[ref.backdrop].backdrop is not None:
            errors.append(
                f"{section}['{key}']: backdrop '{ref.backdrop}' itself has a "
                "backdrop set - chaining isn't supported, point backdrop at "
                "a full-bleed base texture (e.g. plains/floor) directly"
            )
        if section == "tile_kinds" and ref.backdrop == key:
            errors.append(f"tile_kinds['{key}']: backdrop can't reference itself")

    for entity_id, ref in parsed.entities.items():
        if entity_id != PLAYER_ENTITY_ID and entity_id not in catalog.entities:
            errors.append(f"entities['{entity_id}']: unknown entity id")
        if entity_id == PLAYER_ENTITY_ID and ref.recolor:
            errors.append(
                "entities['player']: recolor is only meaningful for a real "
                "catalog entity (the player has no EntityDef/.color field to "
                "tint toward - it's hardcoded in engine/game_map.py)"
            )
        if ref.backdrop is not None:
            errors.append(
                f"entities['{entity_id}']: backdrop is only meaningful for "
                "tile_kinds/dungeon_entrances - an entity/item already gets "
                "this dynamically, composited over whatever tile it's "
                "actually standing on (see _resolved_entity_glyph)"
            )
        _check_sheet("entities", entity_id, ref)

    for item_id, ref in parsed.items.items():
        if item_id not in catalog.items:
            errors.append(f"items['{item_id}']: unknown item id")
        if ref.backdrop is not None:
            errors.append(
                f"items['{item_id}']: backdrop is only meaningful for "
                "tile_kinds/dungeon_entrances - an item already gets this "
                "dynamically, composited over whatever tile it's actually "
                "sitting on (see _resolved_entity_glyph)"
            )
        _check_sheet("items", item_id, ref)

    for kind, ref in parsed.tile_kinds.items():
        if kind not in _VALID_SPRITE_TILE_KINDS:
            errors.append(f"tile_kinds['{kind}']: not a recognized tile kind")
        if ref.recolor:
            errors.append(
                f"tile_kinds['{kind}']: recolor is only meaningful for "
                "entities/items (a tile kind has no .color field to tint "
                "toward - see EntityDef.color/ItemDef.color)"
            )
        _check_sheet("tile_kinds", kind, ref)
        _check_backdrop("tile_kinds", kind, ref)

    for dungeon_id, ref in parsed.dungeon_entrances.items():
        if known_dungeon_ids is not None and dungeon_id not in known_dungeon_ids:
            errors.append(f"dungeon_entrances['{dungeon_id}']: unknown dungeon '{dungeon_id}'")
        if ref.recolor:
            errors.append(
                f"dungeon_entrances['{dungeon_id}']: recolor is only "
                "meaningful for entities/items (no .color field to tint toward)"
            )
        _check_sheet("dungeon_entrances", dungeon_id, ref)
        _check_backdrop("dungeon_entrances", dungeon_id, ref)

    for kind, ref in parsed.decorations.items():
        if kind not in _VALID_DECORATION_KINDS:
            errors.append(f"decorations['{kind}']: not a recognized decoration kind")
        if ref.recolor:
            errors.append(
                f"decorations['{kind}']: recolor is only meaningful for "
                "entities/items (a decoration has no .color field to tint toward)"
            )
        if ref.backdrop is not None:
            errors.append(
                f"decorations['{kind}']: backdrop is only meaningful for "
                "tile_kinds/dungeon_entrances - a decoration already gets this "
                "dynamically, composited over whatever tile it's actually "
                "standing on (see _resolved_decoration_glyph)"
            )
        _check_sheet("decorations", kind, ref)

    for override_id, ref in parsed.tile_sprite_overrides.items():
        if ref.recolor:
            errors.append(
                f"tile_sprite_overrides['{override_id}']: recolor is only "
                "meaningful for entities/items (no .color field to tint toward)"
            )
        _check_sheet("tile_sprite_overrides", override_id, ref)
        _check_backdrop("tile_sprite_overrides", override_id, ref)

    if errors:
        raise ContentValidationError(str(path), errors)

    return SpriteManifest(
        sheets=parsed.sheets, entities=parsed.entities,
        items=parsed.items, tile_kinds=parsed.tile_kinds,
        dungeon_entrances=parsed.dungeon_entrances,
        decorations=parsed.decorations,
        tile_sprite_overrides=parsed.tile_sprite_overrides,
    )


@dataclass
class AudioManifest:
    sfx: dict[str, str]
    music: dict[str, str]


def load_audio_manifest(path: Path) -> AudioManifest:
    """Loads and validates data/audio.yaml (see content/schema.py's
    AudioManifestDef) - a flat mapping from semantic event key (what
    Engine.sound_events/main.py's sync_music actually deal in - see
    engine/audio.py's SoundManager) to a repo-relative audio file path.
    No catalog/dungeon-id cross-checking, unlike load_sprite_manifest -
    the keys are free-standing engine-defined event names, not
    references into other content. File existence is never checked here
    either: SoundManager opens files lazily at play time and no-ops on
    anything missing, so an empty manifest (no audio assets present, e.g.
    under pytest) is always valid."""
    raw = _load_yaml(path) or {}
    try:
        parsed = AudioManifestDef(**raw)
    except ValidationError as e:
        raise ContentValidationError(str(path), [str(e)]) from e
    return AudioManifest(sfx=parsed.sfx, music=parsed.music)


def _parse_map_rows(raw_map: str, legend: dict) -> tuple[list[str], list[str]]:
    """Splits a level/overworld file's raw `map` block into rows and validates
    the purely textual concerns shared by every kind of ASCII map, regardless
    of what the tiles mean: trimming the leading/trailing blank line a YAML
    block scalar commonly introduces, every row being the same width, and
    every symbol used actually being defined in the legend. Returns
    (rows, errors) - what each symbol's tile *means* is caller-specific
    (dungeon vs. overworld), so that dispatch stays in load_level/
    load_overworld rather than here."""
    rows = raw_map.split("\n")
    if rows and rows[0] == "":
        rows = rows[1:]
    if rows and rows[-1] == "":
        rows = rows[:-1]
    width = len(rows[0]) if rows else 0

    errors: list[str] = []
    for y, row in enumerate(rows):
        if len(row) != width:
            errors.append(
                f"map row {y} has length {len(row)}, expected {width} "
                "(all rows must be the same length)"
            )

    used_symbols = {ch for row in rows for ch in row}
    undefined_symbols = used_symbols - set(legend.keys())
    for symbol in sorted(undefined_symbols):
        errors.append(f"symbol '{symbol}' used in map but not defined in legend")

    return rows, errors


def _reachable_tiles(
    tiles: list[list[str]], width: int, height: int, start: tuple[int, int]
) -> set[tuple[int, int]]:
    """8-directional walkable-tile BFS from `start`, respecting TILE_PASSABILITY.
    A door is impassable in that table by default (its closed starting state),
    so this is exactly "everywhere reachable holding no keys at all" - the
    baseline `_check_doors_enclose_something` compares against. 8-directional
    to match the player's actual movement: `MovementAction` (engine/actions.py)
    never blocks a diagonal step for cutting a wall's corner, so a 4-directional
    BFS here would call a diagonal bypass "enclosed" when it's actually walkable
    in real play."""
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not (0 <= nx < width and 0 <= ny < height) or (nx, ny) in seen:
                    continue
                walkable, _ = TILE_PASSABILITY.get(tiles[ny][nx], (True, True))
                if walkable:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
    return seen


def _check_doors_enclose_something(
    tiles: list[list[str]],
    doors: list["DoorSpawn"],
    player_start: tuple[int, int],
    width: int,
    height: int,
) -> list[str]:
    """A locked door only makes sense as a reward gate (see
    docs/content_design_process.md section 3): the point is that whatever is
    directly behind it is unreachable without the key. If every tile next to
    a door is already reachable from player_start with *no* doors open, the
    lock has no effect - almost certainly an accidental second route around
    it, not a deliberate long-way-around design (a real detour still has to
    pass through the door eventually to reach what's immediately behind it)."""
    if not doors:
        return []

    reachable_with_no_keys = _reachable_tiles(tiles, width, height, player_start)

    errors: list[str] = []
    for door in doors:
        far_side = [
            (door.x + dx, door.y + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if not (dx == 0 and dy == 0)
            and 0 <= door.x + dx < width
            and 0 <= door.y + dy < height
            and TILE_PASSABILITY.get(tiles[door.y + dy][door.x + dx], (True, True))[0]
            and (door.x + dx, door.y + dy) not in reachable_with_no_keys
        ]
        if not far_side:
            errors.append(
                f"door at ({door.x}, {door.y}) does not enclose anything - every "
                "tile next to it is already reachable without a key, so the lock "
                "has no effect (an unintended second route around it, not a "
                "deliberate detour)"
            )
    return errors


def load_level(
    path: Path,
    catalog: Catalog,
    known_level_ids: set[str] | None = None,
    require_stairs_down: bool = True,
) -> ParsedLevel:
    """Parses and validates a single level file.

    `known_level_ids`, when provided, is the full set of level ids that exist in
    the dungeon; any stairway's `next_level` not in that set is reported as an
    error. Pass None (the default) to skip that cross-file check, e.g. when
    previewing a single level file in isolation.

    `require_stairs_down` is False for a peaceful, non-progression dungeon
    (a settlement) - see DungeonDef.requires_stairs_down; every real dungeon
    keeps the default.
    """
    raw = _load_yaml(path)
    errors: list[str] = []

    try:
        level = LevelDef(**raw)
    except ValidationError as e:
        raise ContentValidationError(str(path), [str(e)]) from e

    rows, row_errors = _parse_map_rows(level.map, level.legend)
    errors.extend(row_errors)
    width = len(rows[0]) if rows else 0
    height = len(rows)

    tiles: list[list[str]] = []
    entity_spawns: list[EntitySpawn] = []
    item_spawns: list[ItemSpawn] = []
    player_starts: list[tuple[int, int]] = []
    stairs: list[StairsSpawn] = []
    doors: list[DoorSpawn] = []
    tile_descriptions: list[TileDescriptionSpawn] = []
    decoration_spawns: list[DecorationSpawn] = []
    tile_sprite_spawns: list[TileSpriteSpawn] = []

    for y, row in enumerate(rows):
        tile_row: list[str] = []
        for x, symbol in enumerate(row):
            entry = level.legend.get(symbol)
            if entry is None:
                tile_row.append("floor")
                continue

            tile_row.append(entry.tile)

            if entry.description:
                tile_descriptions.append(
                    TileDescriptionSpawn(
                        x=x, y=y, text=entry.description, announce=entry.announce,
                        is_landmark=(entry.tile == "landmark"),
                    )
                )

            if entry.tile == "player_start":
                player_starts.append((x, y))

            if entry.tile == "stairs_down":
                if entry.next_level is not None and known_level_ids is not None:
                    if entry.next_level not in known_level_ids:
                        errors.append(
                            f"legend symbol '{symbol}' stairs_down references "
                            f"unknown level '{entry.next_level}'"
                        )
                stairs.append(
                    StairsSpawn(x=x, y=y, next_level=entry.next_level, kind="stairs_down")
                )

            if entry.tile == "stairs_up":
                if entry.next_level is not None and known_level_ids is not None:
                    if entry.next_level not in known_level_ids:
                        errors.append(
                            f"legend symbol '{symbol}' stairs_up references "
                            f"unknown level '{entry.next_level}'"
                        )
                stairs.append(
                    StairsSpawn(x=x, y=y, next_level=entry.next_level, kind="stairs_up")
                )

            if entry.tile == "dungeon_entrance":
                errors.append(
                    f"legend symbol '{symbol}' is a dungeon_entrance tile, which has no "
                    "meaning inside a dungeon - use a terminal stairs_up to leave instead"
                )

            if entry.tile == "door":
                key_item = catalog.items.get(entry.requires_key)
                if key_item is None:
                    errors.append(
                        f"legend symbol '{symbol}' door references unknown item "
                        f"'{entry.requires_key}'"
                    )
                elif not key_item.is_key:
                    errors.append(
                        f"legend symbol '{symbol}' door requires '{entry.requires_key}', "
                        "which is not a key item (is_key: true)"
                    )
                else:
                    doors.append(DoorSpawn(x=x, y=y, requires_key=entry.requires_key))

            if entry.entity is not None:
                if entry.entity not in catalog.entities:
                    errors.append(
                        f"legend symbol '{symbol}' references unknown entity "
                        f"'{entry.entity}'"
                    )
                elif entry.elite and catalog.entities[entry.entity].ai in PEACEFUL_AI_TYPES:
                    errors.append(
                        f"legend symbol '{symbol}' sets elite: true on '{entry.entity}', "
                        f"which is a peaceful NPC (ai '{catalog.entities[entry.entity].ai}') - "
                        "elite only makes sense for a real hostile encounter"
                    )
                else:
                    entity_spawns.append(
                        EntitySpawn(
                            x=x, y=y, entity=catalog.entities[entry.entity],
                            dialogue=entry.dialogue, flag_dialogue=entry.flag_dialogue,
                            elite=entry.elite,
                        )
                    )

            if entry.item is not None:
                if entry.item not in catalog.items:
                    errors.append(
                        f"legend symbol '{symbol}' references unknown item "
                        f"'{entry.item}'"
                    )
                else:
                    item_spawns.append(
                        ItemSpawn(x=x, y=y, item=catalog.items[entry.item])
                    )

            if entry.decoration is not None:
                decoration_spawns.append(DecorationSpawn(x=x, y=y, kind=entry.decoration))

            if entry.tile_sprite is not None:
                tile_sprite_spawns.append(TileSpriteSpawn(x=x, y=y, sprite_id=entry.tile_sprite))
        tiles.append(tile_row)

    if len(player_starts) != 1:
        errors.append(
            f"map must contain exactly one player_start tile, found {len(player_starts)}"
        )

    if require_stairs_down:
        if not any(s.kind == "stairs_down" for s in stairs):
            errors.append("map must contain at least one stairs_down tile, found 0")
    elif not stairs and not level.open_boundary:
        errors.append(
            "map has requires_stairs_down: false but contains no stairway "
            "(stairs_up or stairs_down) and open_boundary isn't set - "
            "there would be no way to leave"
        )

    if level.open_boundary:
        edge_cells = (
            [(x, 0) for x in range(width)] + [(x, height - 1) for x in range(width)]
            + [(0, y) for y in range(height)] + [(width - 1, y) for y in range(height)]
        )
        if not any(TILE_PASSABILITY.get(tiles[y][x], (True, True))[0] for x, y in edge_cells):
            errors.append(
                "open_boundary is set but no perimeter tile is walkable - "
                "there would be no way to ever reach the edge and leave"
            )

    next_level_targets: dict[str, list[tuple[int, int]]] = {}
    for s in stairs:
        if s.next_level is not None:
            next_level_targets.setdefault(s.next_level, []).append((s.x, s.y))
    for target_id, coords in next_level_targets.items():
        if len(coords) > 1:
            coords_str = " and ".join(f"({x}, {y})" for x, y in coords)
            errors.append(
                f"multiple stairways target level '{target_id}' at {coords_str} - "
                "ambiguous which one is the return path when arriving from that level"
            )

    if len(player_starts) == 1:
        errors.extend(
            _check_doors_enclose_something(tiles, doors, player_starts[0], width, height)
        )

    if errors:
        raise ContentValidationError(str(path), errors)

    return ParsedLevel(
        id=level.id,
        name=level.name,
        width=width,
        height=height,
        tiles=tiles,
        player_start=player_starts[0],
        player_start_tile=level.player_start_tile,
        entity_spawns=entity_spawns,
        item_spawns=item_spawns,
        stairs=stairs,
        doors=doors,
        dungeon_entrances=[],
        tile_descriptions=tile_descriptions,
        open_boundary=level.open_boundary,
        open_boundary_message=level.open_boundary_message,
        dark=level.dark,
        decoration_spawns=decoration_spawns,
        tile_sprite_spawns=tile_sprite_spawns,
    )


@dataclass
class _OverworldCell:
    """One cell's own locally-parsed content (coordinates relative to its
    own top-left corner) - what _parse_overworld_cell produces, before
    load_overworld offsets everything into the assembled world's global
    coordinate space."""

    width: int
    height: int
    tiles: list[list[str]]
    player_starts: list[tuple[int, int]]
    player_start_tile: str
    dungeon_entrances: list[DungeonEntranceSpawn]
    tile_descriptions: list[TileDescriptionSpawn]


def _parse_overworld_cell(
    path: Path, catalog: Catalog, known_dungeon_ids: set[str]
) -> tuple["_OverworldCell | None", list[str]]:
    """Parses and validates one overworld cell file - the same per-cell
    body a single-file overworld used to run once for the whole world,
    now run once per cell, entirely in that cell's own local coordinates.
    Errors are returned rather than raised, so load_overworld can collect
    problems across every cell in one pass; every message is prefixed
    with `path` so it names the actual offending cell file, never the
    umbrella cells.lvl. Returns (None, errors) if the cell's own LevelDef
    doesn't even parse - there's nothing further to check in that case."""
    raw = _load_yaml(path)
    errors: list[str] = []

    try:
        level = LevelDef(**raw)
    except ValidationError as e:
        return None, [f"{path}: {e}"]

    rows, row_errors = _parse_map_rows(level.map, level.legend)
    errors.extend(f"{path}: {message}" for message in row_errors)
    width = len(rows[0]) if rows else 0
    height = len(rows)

    tiles: list[list[str]] = []
    player_starts: list[tuple[int, int]] = []
    dungeon_entrances: list[DungeonEntranceSpawn] = []
    tile_descriptions: list[TileDescriptionSpawn] = []

    for y, row in enumerate(rows):
        tile_row: list[str] = []
        for x, symbol in enumerate(row):
            entry = level.legend.get(symbol)
            if entry is None:
                tile_row.append("floor")
                continue

            tile_row.append(entry.tile)

            if entry.description:
                tile_descriptions.append(
                    TileDescriptionSpawn(
                        x=x, y=y, text=entry.description, announce=entry.announce,
                        is_landmark=(entry.tile == "landmark"),
                    )
                )

            if entry.tile == "player_start":
                player_starts.append((x, y))

            if entry.tile == "dungeon_entrance":
                if entry.dungeon_id not in known_dungeon_ids:
                    errors.append(
                        f"{path}: legend symbol '{symbol}' dungeon_entrance references "
                        f"unknown dungeon '{entry.dungeon_id}'"
                    )
                dungeon_entrances.append(
                    DungeonEntranceSpawn(x=x, y=y, dungeon_id=entry.dungeon_id)
                )

            if entry.tile in ("stairs_down", "stairs_up", "door"):
                errors.append(
                    f"{path}: legend symbol '{symbol}' is a {entry.tile} tile, which has "
                    "no meaning on the overworld - use dungeon_entrance instead"
                )

            if entry.entity is not None or entry.item is not None:
                errors.append(
                    f"{path}: legend symbol '{symbol}' spawns an entity/item, which has "
                    "no meaning on the overworld - there is no combat or itemization here"
                )
        tiles.append(tile_row)

    cell = _OverworldCell(
        width=width, height=height, tiles=tiles,
        player_starts=player_starts, player_start_tile=level.player_start_tile,
        dungeon_entrances=dungeon_entrances, tile_descriptions=tile_descriptions,
    )
    return cell, errors


def load_overworld(overworld_dir: Path, catalog: Catalog, known_dungeon_ids: set[str]) -> ParsedLevel:
    """Parses and validates the overworld - a grid of separately-authored
    cell files (overworld_dir/cells.lvl + overworld_dir/cells/*.lvl)
    stitched into one seamless ParsedLevel at load time. This is purely a
    content-authoring split: nothing downstream (build_game_map/GameMap/
    movement/FOV) is aware cells exist - Engine only ever sees the one
    assembled ParsedLevel this function returns, exactly as if the whole
    overworld had been authored as a single file. Reuses the same
    ParsedLevel shape as a dungeon level so build_game_map/Engine can
    treat it identically; its own tile vocabulary is deliberately
    smaller: no entities, items, doors, or stairs (this is not a
    dungeon), only terrain and dungeon_entrance tiles leading into a
    dungeon registry id (not a level id - that's why this doesn't reuse
    known_level_ids)."""
    manifest_path = overworld_dir / "cells.lvl"
    raw_manifest = _load_yaml(manifest_path)

    try:
        manifest = CellsManifestDef(**raw_manifest)
    except ValidationError as e:
        raise ContentValidationError(str(manifest_path), [str(e)]) from e

    grid_rows, grid_errors = _parse_map_rows(manifest.map, manifest.legend)
    if grid_errors:
        raise ContentValidationError(str(manifest_path), grid_errors)

    grid_height = len(grid_rows)
    grid_width = len(grid_rows[0]) if grid_rows else 0

    errors: list[str] = []
    cells: list[list["_OverworldCell | None"]] = []
    expected_width: int | None = None
    expected_height: int | None = None
    first_cell_id: str | None = None

    for gy, grid_row in enumerate(grid_rows):
        cell_row: list["_OverworldCell | None"] = []
        for symbol in grid_row:
            cell_id = manifest.legend[symbol]
            cell_path = overworld_dir / "cells" / f"{cell_id}.lvl"
            if not cell_path.exists():
                errors.append(
                    f"cells.lvl symbol '{symbol}' references cell '{cell_id}', but "
                    f"'{cell_path}' does not exist"
                )
                cell_row.append(None)
                continue

            cell, cell_errors = _parse_overworld_cell(cell_path, catalog, known_dungeon_ids)
            errors.extend(cell_errors)
            if cell is None:
                cell_row.append(None)
                continue

            if expected_width is None:
                expected_width, expected_height, first_cell_id = cell.width, cell.height, cell_id
            elif (cell.width, cell.height) != (expected_width, expected_height):
                errors.append(
                    f"cell '{cell_id}' ({cell_path}): expected {expected_width}x{expected_height} "
                    f"(cell size set by '{first_cell_id}'), got {cell.width}x{cell.height}"
                )
            cell_row.append(cell)
        cells.append(cell_row)

    if errors:
        raise ContentValidationError(str(overworld_dir), errors)

    # A grid with at least one row/column always has at least one cell, and
    # the loop above always sets expected_width/height off the first one -
    # an all-empty grid would already have failed _parse_map_rows above.
    assert expected_width is not None and expected_height is not None

    tiles: list[list[str]] = []
    for gy in range(grid_height):
        for ly in range(expected_height):
            row: list[str] = []
            for gx in range(grid_width):
                row.extend(cells[gy][gx].tiles[ly])
            tiles.append(row)

    player_starts: list[tuple[int, int]] = []
    player_start_tile = "floor"
    dungeon_entrances: list[DungeonEntranceSpawn] = []
    tile_descriptions: list[TileDescriptionSpawn] = []

    for gy in range(grid_height):
        for gx in range(grid_width):
            cell = cells[gy][gx]
            offset_x, offset_y = gx * expected_width, gy * expected_height
            for x, y in cell.player_starts:
                player_starts.append((x + offset_x, y + offset_y))
                player_start_tile = cell.player_start_tile
            for entrance in cell.dungeon_entrances:
                dungeon_entrances.append(
                    DungeonEntranceSpawn(
                        x=entrance.x + offset_x, y=entrance.y + offset_y,
                        dungeon_id=entrance.dungeon_id,
                    )
                )
            for desc in cell.tile_descriptions:
                tile_descriptions.append(
                    TileDescriptionSpawn(
                        x=desc.x + offset_x, y=desc.y + offset_y, text=desc.text,
                        announce=desc.announce, is_landmark=desc.is_landmark,
                    )
                )

    if len(player_starts) != 1:
        errors.append(
            "overworld must contain exactly one player_start tile across all "
            f"cells, found {len(player_starts)}"
        )

    if not dungeon_entrances:
        errors.append(
            "overworld must contain at least one dungeon_entrance tile across "
            "all cells, found 0"
        )

    dungeon_targets: dict[str, list[tuple[int, int]]] = {}
    for entrance in dungeon_entrances:
        dungeon_targets.setdefault(entrance.dungeon_id, []).append((entrance.x, entrance.y))
    for dungeon_id, coords in dungeon_targets.items():
        if len(coords) > 1:
            coords_str = " and ".join(f"({x}, {y})" for x, y in coords)
            errors.append(
                f"multiple dungeon_entrance tiles target dungeon '{dungeon_id}' at "
                f"{coords_str} - ambiguous which one is the return path when leaving it"
            )

    if errors:
        raise ContentValidationError(str(overworld_dir), errors)

    return ParsedLevel(
        id=manifest.id,
        name=manifest.name,
        width=grid_width * expected_width,
        height=grid_height * expected_height,
        tiles=tiles,
        player_start=player_starts[0],
        player_start_tile=player_start_tile,
        entity_spawns=[],
        item_spawns=[],
        stairs=[],
        doors=[],
        dungeon_entrances=dungeon_entrances,
        tile_descriptions=tile_descriptions,
        open_boundary=False,
        open_boundary_message="",
        dark=False,
    )


def load_levels(
    levels_dir: Path, catalog: Catalog, require_stairs_down: bool = True
) -> dict[str, ParsedLevel]:
    """Loads and validates every `.lvl` file in a directory as one connected
    set of levels. Two passes: first collect every level's id (so stairway
    destinations can be checked), then fully validate each level against
    that known-id set. `require_stairs_down` is forwarded to every
    `load_level` call - see its docstring."""
    paths = sorted(levels_dir.glob("*.lvl"))
    if not paths:
        raise ContentValidationError(str(levels_dir), ["no .lvl files found"])

    known_level_ids: set[str] = set()
    errors: list[str] = []
    for path in paths:
        raw = _load_yaml(path)
        level_id = raw.get("id") if isinstance(raw, dict) else None
        if not level_id:
            errors.append(f"{path}: missing required 'id' field")
            continue
        if level_id in known_level_ids:
            errors.append(f"{path}: duplicate level id '{level_id}'")
        known_level_ids.add(level_id)

    if errors:
        raise ContentValidationError(str(levels_dir), errors)

    levels: dict[str, ParsedLevel] = {}
    for path in paths:
        try:
            level = load_level(
                path, catalog, known_level_ids=known_level_ids,
                require_stairs_down=require_stairs_down,
            )
        except ContentValidationError as e:
            errors.extend(f"{path}: {err}" for err in e.errors)
            continue
        levels[level.id] = level

    if errors:
        raise ContentValidationError(str(levels_dir), errors)

    return levels


@dataclass
class Dungeon:
    """A validated dungeon: its manifest plus every level it contains."""

    id: str
    name: str
    starting_level: str
    description: str
    inspect_text: str
    requires_stairs_down: bool
    ruined_tile: str | None
    ruined_description: str
    ruined_starting_level: str | None
    pre_arrival_starting_level: str | None
    pre_arrival_until_year: int | None
    pre_arrival_until_day: int | None
    balance_reference_xp: int | None
    levels: dict[str, ParsedLevel]


def load_dungeon(dungeon_dir: Path, catalog: Catalog) -> Dungeon:
    """Loads one dungeon: its manifest (`dungeon_dir/dungeon.yaml`) plus
    every level under `dungeon_dir/levels/`."""
    manifest_path = dungeon_dir / "dungeon.yaml"
    raw = _load_yaml(manifest_path)
    try:
        manifest = DungeonDef(**(raw or {}))
    except ValidationError as e:
        raise ContentValidationError(str(manifest_path), [str(e)]) from e

    levels = load_levels(
        dungeon_dir / "levels", catalog, require_stairs_down=manifest.requires_stairs_down
    )

    errors: list[str] = []
    if manifest.starting_level not in levels:
        errors.append(
            f"starting_level '{manifest.starting_level}' is not among "
            "this dungeon's levels"
        )
    if manifest.ruined_starting_level is not None:
        if manifest.ruined_starting_level not in levels:
            errors.append(
                f"ruined_starting_level '{manifest.ruined_starting_level}' is not "
                "among this dungeon's levels"
            )
        elif manifest.ruined_starting_level == manifest.starting_level:
            errors.append(
                "ruined_starting_level is the same as starting_level - a razed "
                "dungeon's entrance would then have no visible effect on the interior"
            )
    if manifest.pre_arrival_starting_level is not None:
        if manifest.pre_arrival_starting_level not in levels:
            errors.append(
                f"pre_arrival_starting_level '{manifest.pre_arrival_starting_level}' is not "
                "among this dungeon's levels"
            )
        elif manifest.pre_arrival_starting_level == manifest.starting_level:
            errors.append(
                "pre_arrival_starting_level is the same as starting_level - entering "
                "before the scheduled date would then have no visible effect on the interior"
            )
    if errors:
        raise ContentValidationError(str(manifest_path), errors)

    return Dungeon(
        id=manifest.id,
        name=manifest.name,
        starting_level=manifest.starting_level,
        description=manifest.description,
        inspect_text=manifest.inspect_text,
        requires_stairs_down=manifest.requires_stairs_down,
        ruined_tile=manifest.ruined_tile,
        ruined_description=manifest.ruined_description,
        ruined_starting_level=manifest.ruined_starting_level,
        pre_arrival_starting_level=manifest.pre_arrival_starting_level,
        pre_arrival_until_year=manifest.pre_arrival_until_year,
        pre_arrival_until_day=manifest.pre_arrival_until_day,
        balance_reference_xp=manifest.balance_reference_xp,
        levels=levels,
    )


def load_dungeon_registry(dungeons_dir: Path, catalog: Catalog) -> dict[str, Dungeon]:
    """Discovers and loads every dungeon under `dungeons_dir` - each an
    immediate subdirectory containing its own `dungeon.yaml` + `levels/`.
    This is what a dungeon-select screen (or a future overworld) would
    enumerate."""
    dungeon_dirs = sorted(p for p in dungeons_dir.iterdir() if p.is_dir())
    if not dungeon_dirs:
        raise ContentValidationError(str(dungeons_dir), ["no dungeon subdirectories found"])

    registry: dict[str, Dungeon] = {}
    errors: list[str] = []
    for dungeon_dir in dungeon_dirs:
        try:
            dungeon = load_dungeon(dungeon_dir, catalog)
        except ContentValidationError as e:
            errors.extend(f"{dungeon_dir}: {err}" for err in e.errors)
            continue
        if dungeon.id in registry:
            errors.append(f"{dungeon_dir}: duplicate dungeon id '{dungeon.id}'")
            continue
        registry[dungeon.id] = dungeon

    if errors:
        raise ContentValidationError(str(dungeons_dir), errors)

    return registry
