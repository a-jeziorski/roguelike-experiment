from pathlib import Path

import pytest

from content.loader import ContentValidationError, load_catalog, load_dungeon_registry, load_region_corruption

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DUNGEONS_DIR = DATA_DIR / "dungeons"
OVERWORLD_DIR = DATA_DIR / "overworld"


def write_corruption(tmp_path: Path, cell_id: str, text: str) -> Path:
    cells_dir = tmp_path / "cells"
    cells_dir.mkdir(parents=True, exist_ok=True)
    path = cells_dir / f"{cell_id}.corruption.yaml"
    path.write_text(text, encoding="utf-8")
    return path


VALID_NORTHERN_STEPPE_YAML = (
    "cell_id: northern_steppe\n"
    "epicenter: [75, 10]\n"
    "phases:\n"
    "  - after_year: 87\n"
    "    after_day: 80\n"
    "    radius: 5\n"
    "  - after_year: 87\n"
    "    after_day: 140\n"
    "    radius: 15\n"
    "    raze_dungeon_id: northern_watch_post\n"
    "  - after_year: 87\n"
    "    after_day: 170\n"
    "    radius: 20\n"
    "    uncover:\n"
    "      - coord: [60, 5]\n"
    "        dungeon_id: elder_dig_site_a\n"
    "      - coord: [75, 10]\n"
    "        dungeon_id: elder_dig_site_b\n"
)


def test_load_region_corruption_returns_empty_dict_when_no_files_exist(tmp_path):
    (tmp_path / "cells").mkdir()
    assert load_region_corruption(tmp_path) == {}


def test_load_region_corruption_returns_empty_dict_when_cells_dir_missing(tmp_path):
    assert load_region_corruption(tmp_path) == {}


def test_load_region_corruption_loads_a_valid_file(tmp_path):
    write_corruption(tmp_path, "northern_steppe", VALID_NORTHERN_STEPPE_YAML)

    defs = load_region_corruption(
        tmp_path,
        known_cell_ids={"northern_steppe", "heartlands"},
        known_dungeon_ids={"northern_watch_post", "elder_dig_site_a", "elder_dig_site_b"},
    )

    assert set(defs) == {"northern_steppe"}
    corruption = defs["northern_steppe"]
    assert corruption.epicenter == (75, 10)
    assert len(corruption.phases) == 3
    assert corruption.phases[1].raze_dungeon_id == "northern_watch_post"
    assert [u.dungeon_id for u in corruption.phases[2].uncover] == [
        "elder_dig_site_a", "elder_dig_site_b",
    ]


def test_load_region_corruption_skips_cross_checks_when_known_ids_are_none(tmp_path):
    write_corruption(tmp_path, "northern_steppe", VALID_NORTHERN_STEPPE_YAML)

    defs = load_region_corruption(tmp_path)

    assert set(defs) == {"northern_steppe"}


def test_load_region_corruption_rejects_unknown_cell_id(tmp_path):
    write_corruption(tmp_path, "northern_steppe", VALID_NORTHERN_STEPPE_YAML)

    with pytest.raises(ContentValidationError, match="unknown overworld cell"):
        load_region_corruption(tmp_path, known_cell_ids={"heartlands"})


def test_load_region_corruption_rejects_unknown_raze_dungeon_id(tmp_path):
    write_corruption(tmp_path, "northern_steppe", VALID_NORTHERN_STEPPE_YAML)

    with pytest.raises(ContentValidationError, match="raze_dungeon_id references unknown dungeon"):
        load_region_corruption(tmp_path, known_dungeon_ids={"elder_dig_site_a", "elder_dig_site_b"})


def test_load_region_corruption_rejects_unknown_uncover_dungeon_id(tmp_path):
    write_corruption(tmp_path, "northern_steppe", VALID_NORTHERN_STEPPE_YAML)

    with pytest.raises(ContentValidationError, match="uncover dungeon_id references unknown dungeon"):
        load_region_corruption(tmp_path, known_dungeon_ids={"northern_watch_post"})


def test_load_region_corruption_rejects_duplicate_cell_id_across_files(tmp_path):
    write_corruption(tmp_path, "northern_steppe", VALID_NORTHERN_STEPPE_YAML)
    # A second file whose *filename* differs but whose own cell_id field
    # collides - the dict is keyed by the field, not the filename, so this
    # must still be caught.
    write_corruption(
        tmp_path, "northern_steppe_2",
        VALID_NORTHERN_STEPPE_YAML.replace(
            "raze_dungeon_id: northern_watch_post", "raze_dungeon_id: northern_watch_post",
        ),
    )

    with pytest.raises(ContentValidationError, match="duplicate corruption def"):
        load_region_corruption(tmp_path)


def test_load_region_corruption_propagates_schema_validation_errors(tmp_path):
    write_corruption(
        tmp_path, "northern_steppe",
        "cell_id: northern_steppe\n"
        "epicenter: [75, 10]\n"
        "phases: []\n",
    )

    with pytest.raises(ContentValidationError, match="must not be empty"):
        load_region_corruption(tmp_path)


def test_load_region_corruption_loads_the_real_shipped_northern_steppe_file():
    """Regression net for data/overworld/cells/northern_steppe.corruption.yaml
    (see docs/visitor_corruption.md) - loads and validates against the
    real catalog/dungeon registry, not a synthetic fixture."""
    catalog = load_catalog()
    dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)

    defs = load_region_corruption(
        OVERWORLD_DIR,
        known_cell_ids={p.stem for p in (OVERWORLD_DIR / "cells").glob("*.lvl")},
        known_dungeon_ids=set(dungeon_registry),
    )

    assert set(defs) == {"northern_steppe"}
    corruption = defs["northern_steppe"]
    assert corruption.epicenter == (100, 8)
    assert len(corruption.phases) == 3
    assert corruption.phases[-1].raze_dungeon_id == "northern_watch_post"
    # Radii only grow, and the razing phase's radius must actually reach
    # the Watch Post's own overworld entrance (75, 72) from the epicenter -
    # otherwise the corruption mechanic and the raze it triggers would be
    # visually disconnected (see the .yaml file's own comments for the
    # Chebyshev-distance reasoning).
    radii = [p.radius for p in corruption.phases]
    assert radii == sorted(radii)
    raze_phase = corruption.phases[-1]
    ex, ey = corruption.epicenter
    assert max(abs(75 - ex), abs(72 - ey)) <= raze_phase.radius
