"""XP-equivalent build math - shared by tools/play_llm.py's `testbuild`
mode and, potentially, tools/preview.py.

The XP/Perks feature (data/perks.yaml, content/schema.py's PerkDef) already
prices a flat stat bonus in XP: weapon_training_1 charges 45 XP for +2
attack, and so on for defense/ranged. That's a real, already-authored price
per stat point - this module reuses it rather than inventing a second,
parallel pricing scheme for gear. A weapon's attack_bonus is "worth" exactly
what a perk granting the same attack would have cost; nothing here is a new
number a content author has to keep in sync by hand.

See docs/content_design_process.md §0s for the full write-up (including the
one known simplification: this averages across every same-stat perk, which
is exact today since there's only one perk per stat - a future tiered perk
with a different per-point rate would need this reconsidered, not just
averaged in blindly).
"""

from __future__ import annotations

from content.loader import Catalog
from content.schema import ItemDef, PerkDef

# The three stats an ItemDef's equipment bonus can improve - PerkDef's own
# field names, since the rate is derived from perk pricing. max_hp is
# deliberately excluded: no ItemDef field grants it, only perks do.
_ITEM_STATS = ("attack", "defense", "ranged_attack")


def _perk_bonus(perk: PerkDef, stat: str) -> int | None:
    return getattr(perk, f"{stat}_bonus")


def stat_point_rate(catalog: Catalog, stat: str) -> float:
    """XP cost per +1 point of `stat` ("attack"/"defense"/"ranged_attack"),
    derived by averaging xp_cost/bonus across every catalog perk that prices
    that one stat. Raises ValueError if no perk prices it at all - nothing
    to derive a rate from."""
    if stat not in _ITEM_STATS:
        raise ValueError(f"stat_point_rate: unknown stat {stat!r} (expected one of {_ITEM_STATS})")
    rates = [
        perk.xp_cost / bonus
        for perk in catalog.perks.values()
        if (bonus := _perk_bonus(perk, stat)) is not None
    ]
    if not rates:
        raise ValueError(
            f"no perk in the catalog prices {stat} - nothing to derive a gear "
            "XP-equivalent rate from (see tools/balance.py's module docstring)"
        )
    return sum(rates) / len(rates)


def gear_xp_equivalent(catalog: Catalog, item: ItemDef) -> float:
    """The XP-equivalent value of one item's equipment bonus. 0.0 for an
    item with no attack_bonus/defense_bonus/ranged_attack_bonus (a potion, a
    key, a quest item, or a trinket - see ItemDef.trinket_effect/
    trinket_bonus) - ItemDef's own not_multiple_equipment_slots validator
    already guarantees at most one of the three flat-stat bonuses is set,
    so at most one term here is ever nonzero. A trinket's percentage-point
    rate bonus deliberately has no XP-equivalent formula yet - there's no
    real playtesting data to calibrate "how much is +1% crit chance worth"
    against a flat attack/defense point the way stat_point_rate already
    is; build_xp_total below doesn't take a trinket_id argument for the
    same reason. Revisit once trinkets have shipped enough to have real
    balance data behind them."""
    total = 0.0
    for stat in _ITEM_STATS:
        bonus = getattr(item, f"{stat}_bonus")
        if bonus:
            total += bonus * stat_point_rate(catalog, stat)
    return total


def build_xp_total(
    catalog: Catalog,
    perk_ids: list[str],
    weapon_id: str | None = None,
    armor_id: str | None = None,
    ranged_id: str | None = None,
) -> float:
    """Total XP-equivalent of a build: each perk's own real xp_cost, plus
    each equipped item's derived gear_xp_equivalent. A None item id
    contributes nothing - not every build needs a ranged weapon."""
    total = sum(catalog.perks[perk_id].xp_cost for perk_id in perk_ids)
    for item_id in (weapon_id, armor_id, ranged_id):
        if item_id is not None:
            total += gear_xp_equivalent(catalog, catalog.items[item_id])
    return total
