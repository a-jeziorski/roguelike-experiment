from pathlib import Path

import pytest

from content.loader import ContentValidationError, load_catalog, load_level

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_load_catalog_loads_real_data():
    catalog = load_catalog()
    assert "rat" in catalog.entities
    assert "goblin" in catalog.entities
    assert "healing_potion" in catalog.items
    assert "rusty_dagger" in catalog.items


@pytest.mark.parametrize("level_file", sorted((DATA_DIR / "levels").glob("*.lvl")))
def test_every_shipped_level_validates_cleanly(level_file):
    catalog = load_catalog()
    level = load_level(level_file, catalog)
    assert level.width > 0
    assert level.height > 0
    assert all(len(row) == level.width for row in level.tiles)


def test_level_01_content():
    catalog = load_catalog()
    level = load_level(DATA_DIR / "levels" / "level_01.lvl", catalog)

    assert level.id == "level_01"
    assert level.next_level is None

    entity_names = sorted(s.entity.name for s in level.entity_spawns)
    assert entity_names == ["Goblin", "Rat", "Rat"]

    item_names = sorted(s.item.name for s in level.item_spawns)
    assert item_names == ["Healing Potion", "Rusty Dagger"]


def test_broken_level_reports_all_errors():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError) as excinfo:
        load_level(FIXTURES_DIR / "broken_level.lvl", catalog)

    message = str(excinfo.value)
    assert "row" in message  # ragged map row
    assert "player_start" in message  # missing player start
    assert "nonexistent_monster" in message  # unknown entity reference
