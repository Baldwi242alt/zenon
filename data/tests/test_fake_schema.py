"""The fake files teammates build on must match the shared schemas exactly."""

import json
from pathlib import Path

from sunchaser_data import schema

FAKE = Path(__file__).resolve().parents[1] / "fake"


def load(name):
    return json.loads((FAKE / name).read_text())


def test_fake_files_match_schema():
    assert schema.check_sites(load("sites.json")) == []
    for site in ("site_a", "site_b", "site_c"):
        assert schema.check_timeline(load(f"timeline_{site}.json")) == []
    assert schema.check_scores(load("scores.json")) == []
    assert schema.check_grid(load("grid_site_a.json")) == []


def test_schema_catches_a_renamed_field():
    sites = load("sites.json")
    sites[0]["latitude"] = sites[0].pop("lat")
    errors = schema.check_sites(sites)
    assert any("missing field 'lat'" in e for e in errors)
    assert any("unexpected field 'latitude'" in e for e in errors)
