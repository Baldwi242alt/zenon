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


def test_demo_grid():
    grids = list(SHARED.glob("grid_*.json"))
    if not grids:
        pytest.skip("no grid built")
    for path in grids:
        g = json.loads(path.read_text())
        assert schema.check_grid(g) == []
        assert path.stat().st_size < 8e6                     # keeps the website fast
        elev = np.array(g["elevation_m"])
        gy, gx = np.gradient(elev, g["cell_size_m"])
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        # Heights are stored to 0.1 m and slopes to 0.1 deg, so recomputing a
        # slope from rounded heights can differ by up to about 0.2 deg.
        assert np.allclose(slope, np.array(g["slope_deg"]), atol=0.25)
        assert g["center"]["lat"] in [s["lat"] for s in sites()]


def test_scores_file():
    path = SHARED / "scores.json"
    if not path.exists():
        pytest.skip("scores not built")
    s = json.loads(path.read_text())
    assert schema.check_scores(s) == []
    assert {r["site"] for r in s["sites"]} == {x["id"] for x in sites()}
    # Survivors first, then usable days.
    keys = [(not r["survives"], -r["usable_days"]) for r in s["sites"]]
    assert keys == sorted(keys)
    # Best landings fall inside the scoring window.
    assert all(s["window_start"] <= r["best_landing"][:10] <= s["window_end"] for r in s["sites"])


@pytest.mark.parametrize("site_id", [s["id"] for s in json.loads((SHARED / "sites.json").read_text())])
def test_windows_match_timeline(site_id):
    path = SHARED / f"windows_{site_id}.json"
    if not path.exists():
        pytest.skip("windows not built")
    from sunchaser_data.metrics import window_metrics
    w = json.loads(path.read_text())
    assert schema.check_windows(w) == []
    rows = json.loads((SHARED / f"timeline_{site_id}.json").read_text())["rows"]
    times = [r["time"] for r in rows]
    assert w["rows"][0]["landing"] == "2027-01-01T00:00Z"
    # Landings are exactly step_h apart.
    gaps = {times.index(b["landing"]) - times.index(a["landing"]) for a, b in zip(w["rows"], w["rows"][1:])}
    assert gaps == {w["step_h"]}
    # Re-score three landings by hand from the timeline and compare.
    crit = {"mission_length_days": w["mission_days"], "usable_day": {"min_sun_hours": 12, "min_contact_hours": 4},
            "max_dark_spell_hours": 18}
    if (SHARED / "criteria.json").exists():
        crit = json.loads((SHARED / "criteria.json").read_text())
    n = int(w["mission_days"] * 24)
    for row in (w["rows"][0], w["rows"][700], w["rows"][-1]):
        i = times.index(row["landing"])
        m = window_metrics([r["sun_frac"] for r in rows[i:i + n]], [r["earth_visible"] for r in rows[i:i + n]], crit)
        assert m["usable_days"] == row["usable_days"] and m["longest_dark_h"] == row["longest_dark_h"]


def test_dsn_only_when_earth_visible():
    for s in sites():
        rows = json.loads((SHARED / f"timeline_{s['id']}.json").read_text())["rows"]
        assert all(r["dsn_station"] is None for r in rows if not r["earth_visible"])
        assert sum(r["dsn_station"] is not None for r in rows) > 0.9 * sum(r["earth_visible"] for r in rows)


def test_validation_against_nasa_maps():
    path = Path(__file__).resolve().parents[1] / "sites" / "validation.json"
    if not path.exists():
        pytest.skip("validation not run")
    v = json.loads(path.read_text())
    s = v["maps"]["summary"]
    # Our 18.6-year averages track NASA's published maps closely across sites.
    assert s["sun_correlation"] > 0.95 and s["earth_correlation"] > 0.95
    assert s["sun_mean_abs_diff_pts"] < 8 and s["earth_mean_abs_diff_pts"] < 8
    # Both real landers touched down in sunlight with Earth in view (they talked to Earth).
    for L in v["landings"]:
        assert L["at_landing"]["sun_frac"] > 0.5 and L["at_landing"]["earth_visible"]


def test_surface_temperatures_are_physical():
    for s in sites():
        rows = json.loads((SHARED / f"timeline_{s['id']}.json").read_text())["rows"]
        T = np.array([r["surface_temp_k"] for r in rows], dtype=float)
        assert np.all((T > 25) & (T < 300))          # polar regolith: never near equatorial noon (~390 K)
        lit = np.array([r["sun_frac"] >= 0.5 for r in rows])
        assert T[lit].mean() > T[~lit].mean()        # sunlit hours are warmer on average
