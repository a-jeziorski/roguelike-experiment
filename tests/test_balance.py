import pytest

from content.loader import load_catalog
from tools.balance import build_xp_total, gear_xp_equivalent, stat_point_rate


def test_stat_point_rate_matches_the_one_perk_pricing_each_item_stat():
    catalog = load_catalog()

    # Each rate is xp_cost / bonus for the single catalog perk pricing that
    # stat today (weapon_training_1/shield_training_1/marksman_training_1) -
    # see data/perks.yaml. Exact, not approximate, while there's one perk
    # per stat (see tools/balance.py's own module docstring).
    assert stat_point_rate(catalog, "attack") == pytest.approx(22.5)
    assert stat_point_rate(catalog, "defense") == pytest.approx(22.5)
    assert stat_point_rate(catalog, "ranged_attack") == pytest.approx(20.0)


def test_stat_point_rate_rejects_an_unknown_stat():
    catalog = load_catalog()

    with pytest.raises(ValueError, match="unknown stat"):
        stat_point_rate(catalog, "max_hp")


def test_gear_xp_equivalent_for_a_weapon_and_an_armor_item():
    catalog = load_catalog()

    assert gear_xp_equivalent(catalog, catalog.items["rusty_dagger"]) == pytest.approx(45.0)
    assert gear_xp_equivalent(catalog, catalog.items["leather_armor"]) == pytest.approx(22.5)


def test_gear_xp_equivalent_is_zero_for_an_item_with_no_equipment_bonus():
    catalog = load_catalog()

    assert gear_xp_equivalent(catalog, catalog.items["healing_potion"]) == 0.0


def test_build_xp_total_sums_perk_cost_and_gear_equivalent():
    catalog = load_catalog()

    total = build_xp_total(
        catalog, perk_ids=["toughness_1"], weapon_id="rusty_dagger", armor_id="leather_armor", ranged_id=None,
    )

    assert total == pytest.approx(catalog.perks["toughness_1"].xp_cost + 45.0 + 22.5)


def test_build_xp_total_ignores_none_item_ids():
    catalog = load_catalog()

    assert build_xp_total(catalog, perk_ids=[], weapon_id=None, armor_id=None, ranged_id=None) == 0.0
