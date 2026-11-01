"""Checks on the real files in shared/ (skipped if a file isn't built yet)."""

import json
from pathlib import Path

import numpy as np
import pytest

from sunchaser_data import schema
from sunchaser_data.sunfrac import sun_visible_fraction

SHARED = Path(__file__).resolve().parents[2] / "shared"


def sites():
    return json.loads((SHARED / "sites.json").read_text())


@pytest.mark.parametrize("site_id", [s["id"] for s in json.loads((SHARED / "sites.json").read_text())])
def test_timeline_is_consistent(site_id):
    path = SHARED / f"timeline_{site_id}.json"
    if not path.exists():
        pytest.skip("timeline not built")
    tl = json.loads(path.read_text())
    assert schema.check_timeline(tl) == []
    rows = tl["rows"]
    assert len(rows) == 8760                      # every hour of 2027
    assert rows[0]["time"] == "2027-01-01T00:00Z" and rows[-1]["time"] == "2027-12-31T23:00Z"

    el = np.array([r["sun_elev_deg"] for r in rows])
    hz = np.array([r["sun_horizon_deg"] for r in rows])
    frac = np.array([r["sun_frac"] for r in rows])
    # sun_frac agrees with the Sun-disk formula (allowing for 2-decimal rounding).
    assert np.max(np.abs(sun_visible_fraction(el, hz) - frac)) < 0.05
    # Physics: the Sun never gets far above the horizon at these latitudes.
    assert np.abs(el).max() < 9
    # Earth visible exactly when Earth's centre clears the horizon.
    ee = np.array([r["earth_elev_deg"] for r in rows])
    eh = np.array([r["earth_horizon_deg"] for r in rows])
    vis = np.array([r["earth_visible"] for r in rows])
    clear = np.abs(ee - eh) > 0.01  # ignore ties created by rounding
    assert np.all(vis[clear] == (ee > eh)[clear])
