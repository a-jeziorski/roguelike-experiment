"""Draws the game map, entities, HUD, and message log onto a tcod Console.

Text that might run longer than the console is wide (monster/item descriptions
especially - they're free-form authored content, length isn't controlled) must
never be handed to console.print() without an explicit width: tcod does not
wrap by default, it silently clips at the console's right edge. Every print in
this module that isn't a single map glyph goes through a width= bound (either
directly via console.print's own wrapping, which returns how many lines it
used, or via textwrap for the message log's "does this still fit" trimming
logic) and every multi-line region uses a running y cursor instead of
hardcoded offsets, so the layout still holds together when something wraps to
more than one line.

The map itself is drawn through a fixed-size camera viewport (VIEWPORT_WIDTH x
VIEWPORT_HEIGHT) rather than 1:1 onto the console: a level's dimensions are
authored content and can exceed the console's size in either direction, so map
coordinates always go through compute_camera() + a `- cam_x, - cam_y`
translation before hitting console.print()/console.rgb - never printed at raw
map coordinates. The HUD is anchored at the fixed row VIEWPORT_HEIGHT + 1,
independent of the map's actual height, for the same reason.

The message log is a separate, independent panel to the right of the map/HUD
column entirely (LOG_PANEL_X onward), spanning the full console height rather
than sharing vertical space with the HUD below the map - a single vertical
"|" divider column (LOG_PANEL_GAP) separates the two. This is deliberate:
earlier the log had to compete with the HUD for a handful of leftover rows
and lost messages during busy turns; giving it its own always-full-height
column plus PageUp/PageDown scrolling (see main.py, clamp_log_scroll_offset
below) fixes that without the HUD's own layout needing to change at all."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import tcod.los

from engine.entity import potion_kind
from engine.targeting import is_valid_target

if TYPE_CHECKING:
    from tcod.console import Console

    from content.loader import Catalog
    from engine.engine import Engine, MessageLog
    from engine.entity import Entity
    from engine.game_map import GameMap
    from engine.quest import Quest
    from engine.sprites import SpriteCodepoints

TILE_VISUALS = {
    "wall": {"glyph": "#", "dark": (35, 35, 55), "light": (100, 100, 130)},
    "floor": {"glyph": ".", "dark": (25, 25, 35), "light": (75, 75, 95)},
    "stairs_down": {"glyph": ">", "dark": (65, 45, 15), "light": (210, 160, 60)},
    "stairs_up": {"glyph": "<", "dark": (65, 45, 15), "light": (210, 160, 60)},
    "door": {"glyph": "+", "dark": (70, 45, 15), "light": (170, 110, 40)},
    # A walkable point of interest (furniture, a landmark) - distinct from
    # both plain floor and from entity/item glyphs so it reads as "look
    # closer here" without being mistaken for something to fight or pick up.
    "landmark": {"glyph": "'", "dark": (95, 80, 55), "light": (200, 175, 130)},
    # Overworld terrain.
    "mountain": {"glyph": "^", "dark": (70, 65, 60), "light": (150, 140, 130)},
    "sea": {"glyph": "~", "dark": (15, 40, 80), "light": (60, 110, 200)},
    "forest": {"glyph": "T", "dark": (20, 50, 25), "light": (60, 140, 60)},
    "road": {"glyph": ".", "dark": (60, 50, 30), "light": (150, 130, 80)},
    "plains": {"glyph": ",", "dark": (35, 45, 20), "light": (120, 150, 70)},
    "town": {"glyph": "n", "dark": (80, 60, 25), "light": (210, 170, 90)},
    "dungeon_entrance": {"glyph": "O", "dark": (90, 60, 10), "light": (255, 200, 60)},
    # Windswept dune sand (see Engine._apply_environmental_hazard) - a warm,
    # sandy gold distinct enough from plains' green at a glance to warn a
    # player before they've taken the first hit of damage.
    "dunes": {"glyph": "\"", "dark": (75, 60, 30), "light": (210, 180, 110)},
}

TILE_DESCRIPTIONS = {
    "wall": "Wall.",
    "floor": "Bare floor.",
    "stairs_down": "Stairs leading down.",
    "stairs_up": "Stairs leading up.",
    "mountain": "Impassable mountains.",
    "sea": "Open water, too deep to cross.",
    "forest": "Dense woodland.",
    "road": "A worn dirt road.",
    "plains": "Open grassland.",
    "town": "A small settlement.",
    "dungeon_entrance": "An entrance leading underground.",
    "landmark": "Something here catches your eye.",
    "dunes": "Loose, shifting sand, scoured bare by a wind that never fully dies down. Standing here for long is a mistake.",
}

HUD_FG = (220, 220, 220)
# One color per MessageLog category (see engine/engine.py's Message) - keeps
# the log scannable now that combat/dialogue/quest features all write to it
# in the same run: combat in red, spoken NPC lines in blue, everything else
# (level transitions, item/door feedback, quest updates - "descriptive" text
# in the same spirit as look mode's) in yellow, and a tile's auto-announced
# description (Engine._log_newly_seen_tile_announcements) in violet - a
# distinct hue from all three, since it's neither urgent (combat) nor
# spoken (dialogue) and shouldn't blend into ordinary system feedback (info).
LOG_COLORS = {
    "combat": (210, 70, 70),
    "dialogue": (100, 150, 230),
    "info": (210, 190, 90),
    "flavor": (170, 130, 200),
}
DEAD_FG = (220, 50, 50)
CURSOR_BG = (90, 90, 20)
TARGET_VALID_BG = (40, 120, 40)
TARGET_INVALID_BG = (110, 40, 40)
PROJECTILE_FG = (255, 230, 120)
IMPACT_BG = (200, 60, 30)

# The map is drawn into this fixed-size window regardless of a level's actual
# size; VIEWPORT_HEIGHT leaves room below it for the HUD (up to ~10 lines)
# within main.py's CONSOLE_ROWS - the message log no longer shares this
# column at all, see LOG_PANEL_* below.
VIEWPORT_WIDTH = 70
VIEWPORT_HEIGHT = 30

# The message log's own vertical panel, to the right of the map/HUD column -
# a single "|" divider column (LOG_PANEL_GAP) separates the two, and the
# panel itself spans the full console height (see render_all/render_look_frame/
# render_target_frame), not just whatever's left below the HUD. main.py's
# CONSOLE_COLUMNS = LOG_PANEL_X + LOG_PANEL_WIDTH.
LOG_PANEL_GAP = 1
LOG_PANEL_WIDTH = 34
LOG_PANEL_X = VIEWPORT_WIDTH + LOG_PANEL_GAP


def compute_camera(
    map_width: int, map_height: int, viewport_width: int, viewport_height: int, focus_x: int, focus_y: int
) -> tuple[int, int]:
    """Top-left map coordinate the viewport should render from, centered on
    (focus_x, focus_y) and clamped so the camera never scrolls past the map's
    edges - or, for a map no bigger than the viewport, never scrolls at all,
    reproducing the old fixed full-map render as the small-map special case."""
    cam_x = focus_x - viewport_width // 2
    cam_y = focus_y - viewport_height // 2
    cam_x = max(0, min(cam_x, max(0, map_width - viewport_width)))
    cam_y = max(0, min(cam_y, max(0, map_height - viewport_height)))
    return cam_x, cam_y


def _resolved_glyph(fallback_glyph: str, key: str, lookup: "dict[str, int] | None") -> str:
    """The one place the sprite-vs-ASCII fallback decision is made. `lookup`
    is None (no sprite manifest loaded) or a dict with no entry for `key`
    (nothing mapped for this id/kind yet) - both fall through to the
    literal authored ASCII glyph, never a missing-glyph box, never a crash.
    An empty `key` always falls back too, regardless of `lookup`'s contents:
    no catalog id (or reserved id - see content.loader.PLAYER_ENTITY_ID) is
    ever "", so a sprite entry keyed by "" could never be an intentional
    mapping for anything."""
    if key and lookup is not None and key in lookup:
        return chr(lookup[key])
    return fallback_glyph


def _resolved_tile_glyph(
    kind: str, x: int, y: int, game_map: "GameMap", sprite_codepoints: "SpriteCodepoints | None"
) -> str:
    """The tile-kind counterpart to _resolved_entity_glyph: every kind
    behaves exactly like _resolved_glyph, except a dungeon_entrance cell
    prefers a sprite specific to the dungeon it leads to
    (game_map.dungeon_entrances[(x,y)]) over the generic dungeon_entrance
    tile-kind sprite - falling back to that generic sprite, then to ASCII,
    exactly like every other per-cell resolution in this file."""
    if kind == "dungeon_entrance" and sprite_codepoints is not None:
        dungeon_id = game_map.dungeon_entrances.get((x, y))
        codepoint = sprite_codepoints.dungeon_entrances.get(dungeon_id) if dungeon_id else None
        if codepoint is not None:
            return chr(codepoint)
    tile_kinds = sprite_codepoints.tile_kinds if sprite_codepoints is not None else None
    return _resolved_glyph(TILE_VISUALS[kind]["glyph"], kind, tile_kinds)


def render_map(
    console: "Console",
    game_map: "GameMap",
    cam_x: int,
    cam_y: int,
    sprite_codepoints: "SpriteCodepoints | None" = None,
) -> None:
    visible_width = min(VIEWPORT_WIDTH, game_map.width - cam_x)
    visible_height = min(VIEWPORT_HEIGHT, game_map.height - cam_y)
    for sx in range(visible_width):
        x = cam_x + sx
        for sy in range(visible_height):
            y = cam_y + sy
            kind = game_map.kinds[x, y]
            visual = TILE_VISUALS[kind]
            glyph = _resolved_tile_glyph(kind, x, y, game_map, sprite_codepoints)
            if game_map.visible[x, y]:
                console.print(sx, sy, glyph, fg=visual["light"])
            elif game_map.explored[x, y]:
                console.print(sx, sy, glyph, fg=visual["dark"])


def _resolved_entity_glyph(
    entity: "Entity", tile_kind: str, sprite_codepoints: "SpriteCodepoints | None"
) -> str:
    """The entity/item counterpart to _resolved_glyph, with one extra level:
    (1) no sprite_codepoints, or no plain sprite mapped for entity.entity_id
    at all -> the authored ASCII glyph; (2) a plain sprite exists but there's
    no composite registered for (entity.entity_id, tile_kind) - because
    tile_kind itself has no sprite mapped (e.g. mountain, deliberately) ->
    the entity's plain, uncomposited sprite (today's look - a real but rare
    cosmetic gap only in that edge case, never ASCII, never a crash); (3)
    both mapped -> the entity composited over tile_kind's own sprite (see
    engine/sprites.py's composite_sprite_over_terrain), so the real terrain
    shows through the sprite's transparent background instead of a plain
    black square."""
    if not entity.entity_id or sprite_codepoints is None:
        return entity.glyph
    is_item = entity.item is not None
    plain_lookup = sprite_codepoints.items if is_item else sprite_codepoints.entities
    if entity.entity_id not in plain_lookup:
        return entity.glyph
    composited_lookup = sprite_codepoints.items_on_tile if is_item else sprite_codepoints.entities_on_tile
    composited = composited_lookup.get((entity.entity_id, tile_kind))
    return chr(composited) if composited is not None else chr(plain_lookup[entity.entity_id])


def render_entities(
    console: "Console",
    game_map: "GameMap",
    cam_x: int,
    cam_y: int,
    sprite_codepoints: "SpriteCodepoints | None" = None,
) -> None:
    for entity in sorted(game_map.entities, key=lambda e: e.render_priority):
        if not game_map.visible[entity.x, entity.y]:
            continue
        sx, sy = entity.x - cam_x, entity.y - cam_y
        if 0 <= sx < VIEWPORT_WIDTH and 0 <= sy < VIEWPORT_HEIGHT:
            tile_kind = game_map.kinds[entity.x, entity.y]
            glyph = _resolved_entity_glyph(entity, tile_kind, sprite_codepoints)
            console.print(sx, sy, glyph, fg=entity.color)


def projectile_glyph(fx: int, fy: int, tx: int, ty: int) -> str:
    """Picks a glyph matching a shot's line of travel, so a flying arrow/bolt
    reads as a directional streak rather than a generic marker."""
    dx, dy = tx - fx, ty - fy
    if dx == 0:
        return "|"
    if dy == 0:
        return "-"
    return "\\" if (dx > 0) == (dy > 0) else "/"


def projectile_path(fx: int, fy: int, tx: int, ty: int) -> list[tuple[int, int]]:
    """Cells a projectile crosses, from just past the shooter through the
    target. The shooter's own tile is excluded so the glyph never draws on
    top of them."""
    return [(int(x), int(y)) for x, y in tcod.los.bresenham((fx, fy), (tx, ty)).tolist()[1:]]


def render_projectile(console: "Console", cam_x: int, cam_y: int, x: int, y: int, glyph: str) -> None:
    sx, sy = x - cam_x, y - cam_y
    if 0 <= sx < VIEWPORT_WIDTH and 0 <= sy < VIEWPORT_HEIGHT:
        console.print(sx, sy, glyph, fg=PROJECTILE_FG)


def flash_impact(console: "Console", game_map: "GameMap", cam_x: int, cam_y: int, x: int, y: int) -> None:
    sx, sy = x - cam_x, y - cam_y
    if 0 <= sx < VIEWPORT_WIDTH and 0 <= sy < VIEWPORT_HEIGHT:
        _print_highlighted_cell(console, game_map, sx, sy, x, y, IMPACT_BG)


def render_hud(console: "Console", engine: "Engine", y: int) -> int:
    """Prints the HUD starting at row y, wrapping any line too long for the
    console. Returns the row just past the last line printed, so callers can
    place whatever comes next without assuming a fixed HUD height. Confined
    to VIEWPORT_WIDTH (not console.width) so HUD text never wraps into the
    message log panel's own columns to the right."""
    width = VIEWPORT_WIDTH
    player = engine.player
    fighter = player.fighter
    inventory = player.inventory
    healing_potions = sum(1 for it in inventory if potion_kind(it.item) == "healing")
    teleport_potions = sum(1 for it in inventory if potion_kind(it.item) == "teleport")
    selected_potion = player.selected_potion_kind
    keys = sum(1 for it in inventory if it.item.key_id)
    ammo = sum(it.item.quantity for it in inventory if it.item.is_ammo)
    weapon_name = player.equipped_weapon.name if player.equipped_weapon else "none"
    armor_name = player.equipped_armor.name if player.equipped_armor else "none"
    ranged_name = player.equipped_ranged_weapon.name if player.equipped_ranged_weapon else "none"

    y += console.print(0, y, engine.level_name, fg=HUD_FG, width=width)
    y += console.print(0, y, engine.clock.format_for_hud(), fg=HUD_FG, width=width)
    active_quest = engine.quest_log.active_quest()
    if active_quest is not None:
        y += console.print(0, y, active_quest.format_for_hud(), fg=HUD_FG, width=width)
    y += console.print(0, y, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG, width=width)
    if fighter.poison_turns_remaining > 0:
        y += console.print(
            0, y,
            f"POISONED: {fighter.poison_damage_per_turn} dmg/turn "
            f"({fighter.poison_turns_remaining} turn(s) left)",
            fg=HUD_FG, width=width,
        )
    y += console.print(
        0,
        y,
        f"ATK: {player.effective_attack}  DEF: {player.effective_defense}",
        fg=HUD_FG,
        width=width,
    )
    y += console.print(
        0,
        y,
        f"Weapon: {weapon_name}  Armor: {armor_name}  Ranged: {ranged_name}",
        fg=HUD_FG,
        width=width,
    )
    healing_marker = ">" if selected_potion == "healing" else " "
    teleport_marker = ">" if selected_potion == "teleport" else " "
    y += console.print(
        0, y,
        f"Potions: {healing_marker}Healing {healing_potions} "
        f"{teleport_marker}Teleport {teleport_potions}  "
        f"Keys: {keys}  Ammo: {ammo}  Gold: {player.gold}  XP: {player.xp}",
        fg=HUD_FG, width=width,
    )
    y += console.print(0, y, "Press [h] for help.", fg=HUD_FG, width=width)
    if engine.game_state == "dead":
        y += console.print(
            0, y, "You have died. [r] play again  [esc] quit", fg=DEAD_FG, width=width
        )

    return y


def _wrap_message_log(message_log: "MessageLog", width: int) -> list[tuple[str, str]]:
    """Every message, oldest to newest, wrapped to width and paired with its
    category - the shared computation behind render_message_log and
    clamp_log_scroll_offset, so wrapping logic never drifts between them."""
    lines: list[tuple[str, str]] = []
    for message in message_log.messages:
        wrapped = textwrap.wrap(message, width) or [message]
        lines.extend((line, message.category) for line in wrapped)
    return lines


def clamp_log_scroll_offset(message_log: "MessageLog", width: int, height: int, offset: int) -> int:
    """Keeps a message-log scroll offset within [0, as-far-back-as-history-
    actually-goes] - 0 means "showing the most recent messages," a larger
    value means further back. Exposed separately from render_message_log so
    main.py can clamp after each PageUp/PageDown (see engine/actions.py's
    ScrollLogAction) without re-deriving the wrapping/height math itself."""
    max_offset = max(0, len(_wrap_message_log(message_log, width)) - height)
    return max(0, min(offset, max_offset))


def render_message_log(
    console: "Console", message_log: "MessageLog", x: int, y: int, width: int, height: int,
    scroll_offset: int = 0,
) -> None:
    """Fills a width x height panel starting at (x, y) with message history,
    newest at the bottom - scroll_offset (see clamp_log_scroll_offset) shows
    further back in history instead of the tail end. Each wrapped line keeps
    its source message's category (LOG_COLORS) so a message that wraps to
    two lines doesn't lose its color partway through."""
    lines = _wrap_message_log(message_log, width)
    scroll_offset = max(0, min(scroll_offset, max(0, len(lines) - height)))
    end = len(lines) - scroll_offset
    start = max(0, end - height)
    for i, (line, category) in enumerate(lines[start:end]):
        console.print(x, y + i, line, fg=LOG_COLORS.get(category, LOG_COLORS["info"]), width=width)


def render_all(console: "Console", engine: "Engine", log_scroll_offset: int = 0) -> None:
    console.clear()
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        engine.player.x, engine.player.y,
    )
    render_map(console, engine.game_map, cam_x, cam_y, engine.sprite_codepoints)
    render_entities(console, engine.game_map, cam_x, cam_y, engine.sprite_codepoints)

    hud_y = VIEWPORT_HEIGHT + 1
    render_hud(console, engine, hud_y)

    for row in range(console.height):
        console.print(VIEWPORT_WIDTH, row, "|", fg=HUD_FG)
    render_message_log(
        console, engine.message_log, LOG_PANEL_X, 0, LOG_PANEL_WIDTH, console.height, log_scroll_offset,
    )


def describe_tile(
    game_map: "GameMap",
    catalog: "Catalog",
    x: int,
    y: int,
    dungeon_inspect_text: "dict[str, str] | None" = None,
) -> list[str]:
    """The lines of text look mode shows for a map coordinate. Pure data in,
    strings out - no console/rendering dependency, so it's unit-testable on
    its own."""
    if not game_map.explored[x, y]:
        return ["You haven't explored this area."]

    kind = game_map.kinds[x, y]
    tile_description = game_map.tile_descriptions.get((x, y))
    if tile_description:
        # An author-supplied override (a legend entry's `description`) wins
        # over every kind-specific default below - most specific wins.
        lines = [tile_description]
    elif kind == "door":
        key_id = game_map.locked_doors.get((x, y))
        key_name = catalog.items[key_id].name if key_id in catalog.items else key_id
        lines = [f"Locked door. Requires: {key_name}."]
    elif kind == "dungeon_entrance":
        dungeon_id = game_map.dungeon_entrances.get((x, y))
        custom_text = (dungeon_inspect_text or {}).get(dungeon_id) if dungeon_id else None
        lines = [custom_text or TILE_DESCRIPTIONS.get(kind, f"{kind.capitalize()}.")]
    else:
        lines = [TILE_DESCRIPTIONS.get(kind, f"{kind.capitalize()}.")]

    if not game_map.visible[x, y]:
        return lines

    for entity in game_map.entities:
        if entity.x != x or entity.y != y:
            continue
        line = entity.name
        if entity.description:
            line += f": {entity.description}"
        if entity.fighter is not None:
            line += f" (HP: {entity.fighter.hp}/{entity.fighter.max_hp})"
        lines.append(line)

    return lines


def render_look_hud(
    console: "Console", engine: "Engine", cursor_x: int, cursor_y: int, y: int
) -> int:
    """Mirrors render_hud's contract: prints starting at y, wraps long lines,
    and returns the row just past the last line printed. Confined to
    VIEWPORT_WIDTH, same reasoning as render_hud."""
    width = VIEWPORT_WIDTH
    player = engine.player
    fighter = player.fighter
    weapon_name = player.equipped_weapon.name if player.equipped_weapon else "none"
    armor_name = player.equipped_armor.name if player.equipped_armor else "none"
    ranged_name = player.equipped_ranged_weapon.name if player.equipped_ranged_weapon else "none"

    y += console.print(0, y, engine.level_name, fg=HUD_FG, width=width)
    y += console.print(0, y, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG, width=width)
    if fighter.poison_turns_remaining > 0:
        y += console.print(
            0, y,
            f"POISONED: {fighter.poison_damage_per_turn} dmg/turn "
            f"({fighter.poison_turns_remaining} turn(s) left)",
            fg=HUD_FG, width=width,
        )
    y += console.print(
        0,
        y,
        f"ATK: {player.effective_attack}  DEF: {player.effective_defense}",
        fg=HUD_FG,
        width=width,
    )
    y += console.print(
        0,
        y,
        f"Weapon: {weapon_name}  Armor: {armor_name}  Ranged: {ranged_name}",
        fg=HUD_FG,
        width=width,
    )

    for line in describe_tile(
        engine.game_map, engine.catalog, cursor_x, cursor_y, engine.dungeon_inspect_text
    ):
        y += console.print(0, y, line, fg=HUD_FG, width=width)

    y += console.print(
        0, y, "[arrows/numpad] move cursor  [l/esc] exit look", fg=HUD_FG, width=width
    )
    return y


def _ascii_cell_visual(game_map: "GameMap", x: int, y: int) -> tuple[str, tuple[int, int, int]] | None:
    """What (x, y) would show under pure-ASCII rendering, ignoring any
    sprite entirely: the topmost visible entity's glyph/color if any
    (matching render_entities' own render_priority ordering), else the
    tile kind's own glyph (light if currently visible, dark if only
    explored). None if the cell is neither visible nor explored -
    render_map/render_entities draw nothing there either."""
    if game_map.visible[x, y]:
        entities_here = [e for e in game_map.entities if e.x == x and e.y == y]
        if entities_here:
            topmost = max(entities_here, key=lambda e: e.render_priority)
            return topmost.glyph, topmost.color
        kind = game_map.kinds[x, y]
        return TILE_VISUALS[kind]["glyph"], TILE_VISUALS[kind]["light"]
    if game_map.explored[x, y]:
        kind = game_map.kinds[x, y]
        return TILE_VISUALS[kind]["glyph"], TILE_VISUALS[kind]["dark"]
    return None


def _print_highlighted_cell(
    console: "Console", game_map: "GameMap", sx: int, sy: int, x: int, y: int,
    bg_color: tuple[int, int, int],
) -> None:
    """Reverts a single cell to its ASCII glyph before applying a bg
    highlight - a fully opaque bitmap tile (every mapped sprite is opaque,
    whether it's plain terrain or an entity composited over its terrain -
    see engine/sprites.py) would otherwise completely cover any bg color
    set on top of it, since a Console cell holds only one glyph and tcod
    draws that glyph's own pixels over the cell's bg, not blended with it.
    The only three places a background highlight is ever applied - look
    mode, target mode, and flash_impact - all go through this."""
    visual = _ascii_cell_visual(game_map, x, y)
    if visual is not None:
        glyph, color = visual
        console.print(sx, sy, glyph, fg=color)
    console.rgb[sx, sy]["bg"] = bg_color


def render_look_frame(console: "Console", engine: "Engine", cursor_x: int, cursor_y: int) -> None:
    """Centers the camera on the cursor rather than the player: look mode's
    cursor can roam anywhere on the map, unlike targeting's range-limited one,
    so it - not the player - is what must stay in view here."""
    console.clear()
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        cursor_x, cursor_y,
    )
    render_map(console, engine.game_map, cam_x, cam_y, engine.sprite_codepoints)
    render_entities(console, engine.game_map, cam_x, cam_y, engine.sprite_codepoints)
    _print_highlighted_cell(
        console, engine.game_map, cursor_x - cam_x, cursor_y - cam_y, cursor_x, cursor_y, CURSOR_BG
    )

    hud_y = VIEWPORT_HEIGHT + 1
    render_look_hud(console, engine, cursor_x, cursor_y, hud_y)

    for row in range(console.height):
        console.print(VIEWPORT_WIDTH, row, "|", fg=HUD_FG)
    render_message_log(console, engine.message_log, LOG_PANEL_X, 0, LOG_PANEL_WIDTH, console.height)


def render_target_hud(
    console: "Console",
    engine: "Engine",
    cursor_x: int,
    cursor_y: int,
    max_range: int,
    y: int,
) -> int:
    """Mirrors render_hud's contract: prints starting at y, wraps long lines,
    and returns the row just past the last line printed. Confined to
    VIEWPORT_WIDTH, same reasoning as render_hud."""
    width = VIEWPORT_WIDTH
    fighter = engine.player.fighter

    y += console.print(0, y, engine.level_name, fg=HUD_FG, width=width)
    y += console.print(0, y, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG, width=width)
    if fighter.poison_turns_remaining > 0:
        y += console.print(
            0, y,
            f"POISONED: {fighter.poison_damage_per_turn} dmg/turn "
            f"({fighter.poison_turns_remaining} turn(s) left)",
            fg=HUD_FG, width=width,
        )

    if is_valid_target(engine.game_map, engine.player, cursor_x, cursor_y, max_range):
        target = engine.game_map.blocking_entity_at(cursor_x, cursor_y)
        status = f"Target: {target.name} (HP: {target.fighter.hp}/{target.fighter.max_hp})"
    else:
        status = "No valid target there."
    y += console.print(0, y, status, fg=HUD_FG, width=width)

    y += console.print(
        0, y, "[arrows/numpad] aim  [f] fire  [esc] cancel", fg=HUD_FG, width=width
    )
    return y


def render_target_frame(
    console: "Console", engine: "Engine", cursor_x: int, cursor_y: int, max_range: int
) -> None:
    console.clear()
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        cursor_x, cursor_y,
    )
    render_map(console, engine.game_map, cam_x, cam_y, engine.sprite_codepoints)
    render_entities(console, engine.game_map, cam_x, cam_y, engine.sprite_codepoints)

    valid = is_valid_target(engine.game_map, engine.player, cursor_x, cursor_y, max_range)
    _print_highlighted_cell(
        console, engine.game_map, cursor_x - cam_x, cursor_y - cam_y, cursor_x, cursor_y,
        TARGET_VALID_BG if valid else TARGET_INVALID_BG,
    )

    hud_y = VIEWPORT_HEIGHT + 1
    render_target_hud(console, engine, cursor_x, cursor_y, max_range, hud_y)

    for row in range(console.height):
        console.print(VIEWPORT_WIDTH, row, "|", fg=HUD_FG)
    render_message_log(console, engine.message_log, LOG_PANEL_X, 0, LOG_PANEL_WIDTH, console.height)


def render_quest_log(
    console: "Console",
    quests: "list[Quest]",
    selected: int,
    active_quest_id: str | None,
    description: str,
) -> None:
    """The quest log screen: unlike every other render_* function above, this
    one draws no map - just a list of known quests (already filtered by the
    caller to exclude not-given ones), the selected quest's description, and
    a footer control hint. `quests` and `selected` together identify the
    highlighted row; `active_quest_id` marks which one is currently pinned to
    the HUD. `description` is the selected quest's already-resolved current
    text (see Quest.current_description) - this function never computes it
    itself, same "engine computes, render just displays" split as
    Engine.shop_price/render_shop's `prices`."""
    console.clear()
    width = console.width
    y = 0
    y += console.print(0, y, "Quest Log", fg=HUD_FG, width=width)
    y += 1

    for i, quest in enumerate(quests):
        marker = ">" if i == selected else " "
        tag = " [ACTIVE]" if quest.id == active_quest_id else ""
        y += console.print(0, y, f"{marker} {quest.format_for_hud()}{tag}", fg=HUD_FG, width=width)

    y += 1
    if quests:
        y += console.print(0, y, description, fg=HUD_FG, width=width)

    y = console.height - 1
    console.print(
        0, y, "[up/down] select  [enter] set active  [q/esc] exit", fg=HUD_FG, width=width
    )


def render_continue_prompt(console: "Console") -> None:
    """The startup "continue a saved game?" screen - like render_quest_log,
    draws no map, just text and a footer hint. No selection/cursor state at
    all (a plain yes/no, not a navigable list), so unlike every other mode
    screen this one takes no extra params beyond the console itself."""
    console.clear()
    width = console.width
    y = console.height // 2 - 1
    y += console.print(0, y, "A saved game was found.", fg=HUD_FG, width=width)
    y += console.print(0, y, "Continue it?", fg=HUD_FG, width=width)

    y = console.height - 1
    console.print(0, y, "[y] continue saved game  [n] start a new game", fg=HUD_FG, width=width)


def render_help(console: "Console") -> None:
    """The help screen: a static keybinding reference sheet, same "no map,
    no engine state needed" shape as render_continue_prompt. Grouped by
    purpose (movement, actions, screens, other) rather than listed
    alphabetically, so a player scanning for "how do I talk to someone"
    finds it under Actions instead of hunting for T. Kept in sync by hand
    with engine/input_handlers.py's actual bindings - there's no single
    source of truth to generate this from, so a new keybinding needs a
    line added here too."""
    console.clear()
    width = console.width
    y = 0
    y += console.print(0, y, "Help - Controls", fg=HUD_FG, width=width)
    y += 1

    def section(title: str) -> None:
        nonlocal y
        y += console.print(0, y, title, fg=HUD_FG, width=width)

    def binding(keys: str, description: str) -> None:
        nonlocal y
        y += console.print(2, y, f"{keys:<22}{description}", fg=HUD_FG, width=width - 2)

    section("Movement")
    binding("Arrows / Numpad", "Move, or attack whatever's in the way")
    binding("Numpad 5 / .", "Wait one turn")
    y += 1

    section("Actions")
    binding("g", "Pick up whatever's underfoot")
    binding("u", "Use/drink the selected potion")
    binding("c", "Cycle which potion kind 'u' drinks")
    binding("f", "Aim and fire an equipped ranged weapon")
    binding("l", "Look around - inspect any tile")
    binding("t", "Talk to an adjacent NPC")
    binding("Page Up / Page Down", "Scroll the message log")
    y += 1

    section("Screens")
    binding("q", "Quest log")
    binding("b", "Shop - buy from an adjacent trader")
    binding("p", "Trainer - learn perks from an adjacent trainer")
    binding("s", "Save the game")
    binding("h", "This help screen")
    y += 1

    section("Other")
    binding("r", "Restart (only once you've died)")
    binding("esc", "Cancel a screen / quit the game")
    y += 1

    section("Notes")
    y += console.print(
        2, y, "Walking into a hostile monster attacks it.", fg=HUD_FG, width=width - 2
    )
    y += console.print(
        2, y,
        "Walking into a still-peaceful NPC asks for confirmation first -",
        fg=HUD_FG, width=width - 2,
    )
    y += console.print(
        2, y, "attacking one turns every guard nearby hostile.", fg=HUD_FG, width=width - 2
    )

    y = console.height - 1
    console.print(0, y, "[h/esc] exit", fg=HUD_FG, width=width)


def render_confirm_attack_prompt(console: "Console", engine: "Engine", entity_name: str) -> None:
    """Overlays a deliberate-attack confirmation on top of the normal game
    view - unlike render_continue_prompt (which runs before any game state
    exists, so it draws a blank screen), this happens mid-run, so the
    player should still see the map/HUD/log they were just looking at,
    including the NPC in question. Shown whenever a BumpAction would
    resolve to attacking a still-peaceful NPC (see
    Engine.would_attack_peaceful_npc) instead of attacking outright - see
    main.py's run_confirm_attack_mode. Printed right after the HUD's own
    content (confined to VIEWPORT_WIDTH), not at the console's bottom rows -
    those now belong to the message log panel, which spans the full console
    height."""
    render_all(console, engine)
    y = render_hud(console, engine, VIEWPORT_HEIGHT + 1) + 1
    console.print(0, y, f"Attack {entity_name}? They aren't hostile.", fg=HUD_FG, width=VIEWPORT_WIDTH)
    console.print(0, y + 1, "[y] attack  [n/esc] cancel", fg=HUD_FG, width=VIEWPORT_WIDTH)


def render_shop(
    console: "Console",
    catalog: "Catalog",
    item_ids: "list[str]",
    prices: "dict[str, int]",
    selected: int,
    player_gold: int,
    status: str,
) -> None:
    """The shop screen: mirrors render_quest_log's shape - no map drawn,
    just a list of what's for sale (item_ids, resolved against the catalog
    for name/description; `prices` gives each one's current effective cost -
    already discount-adjusted by Engine.shop_price, so this function never
    computes a price itself), the selected item's description, a status
    line for the last purchase attempt (this screen never renders the
    message log, so this is the only way to show immediate feedback), and a
    footer control hint."""
    console.clear()
    width = console.width
    y = 0
    y += console.print(0, y, "Shop", fg=HUD_FG, width=width)
    y += console.print(0, y, f"Your gold: {player_gold}", fg=HUD_FG, width=width)
    y += 1

    for i, item_id in enumerate(item_ids):
        idef = catalog.items[item_id]
        cost = prices[item_id]
        marker = ">" if i == selected else " "
        afford_tag = "" if player_gold >= cost else " (can't afford)"
        y += console.print(
            0, y, f"{marker} {idef.name} - {cost} gold{afford_tag}", fg=HUD_FG, width=width
        )

    y += 1
    if item_ids:
        y += console.print(0, y, catalog.items[item_ids[selected]].description, fg=HUD_FG, width=width)

    if status:
        y += 1
        y += console.print(0, y, status, fg=HUD_FG, width=width)

    y = console.height - 1
    console.print(
        0, y, "[up/down] select  [enter] buy  [b/esc] exit", fg=HUD_FG, width=width
    )


def render_trainer(
    console: "Console",
    catalog: "Catalog",
    perk_ids: "list[str]",
    selected: int,
    player_xp: int,
    player_gold: int,
    learned_perk_ids: "set[str]",
    status: str,
) -> None:
    """The trainer screen: mirrors render_shop's shape exactly - no map
    drawn, just a list of what's teachable (perk_ids, resolved against the
    catalog for name/description/cost), the selected perk's description, a
    status line for the last learn attempt (this screen never renders the
    message log, so this is the only way to show immediate feedback), and
    a footer control hint. Every perk in perk_ids is shown regardless of
    whether it's already learned or affordable - same "show everything,
    let the attempt fail gracefully" style as render_shop, rather than
    filtering the list."""
    console.clear()
    width = console.width
    y = 0
    y += console.print(0, y, "Trainer", fg=HUD_FG, width=width)
    y += console.print(0, y, f"Your XP: {player_xp}  Your gold: {player_gold}", fg=HUD_FG, width=width)
    y += 1

    for i, perk_id in enumerate(perk_ids):
        pdef = catalog.perks[perk_id]
        marker = ">" if i == selected else " "
        cost = f"{pdef.xp_cost} XP"
        if pdef.gold_cost:
            cost += f" + {pdef.gold_cost} gold"
        if perk_id in learned_perk_ids:
            tag = " (learned)"
        elif player_xp < pdef.xp_cost or player_gold < (pdef.gold_cost or 0):
            tag = " (can't afford)"
        else:
            tag = ""
        y += console.print(0, y, f"{marker} {pdef.name} - {cost}{tag}", fg=HUD_FG, width=width)

    y += 1
    if perk_ids:
        y += console.print(0, y, catalog.perks[perk_ids[selected]].description, fg=HUD_FG, width=width)

    if status:
        y += 1
        y += console.print(0, y, status, fg=HUD_FG, width=width)

    y = console.height - 1
    console.print(
        0, y, "[up/down] select  [enter] learn  [p/esc] exit", fg=HUD_FG, width=width
    )
