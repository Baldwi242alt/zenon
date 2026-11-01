"""Generate FAKE shared files so teammates can build before real data lands.

Run from the repo root:  python data/fake/make_fake.py

Writes into data/fake/ (never into shared/):
  sites.json, timeline_site_a.json, timeline_site_b.json, timeline_site_c.json,
  grid_site_a.json, scores.json

THESE ARE NOT NASA DATA. The Sun and Earth motion is a simple made-up model
that only mimics the south-pole behaviour (Sun skimming the horizon and
circling once per lunar day, Earth bobbing up and down with libration).
Site names say "FAKE" so nobody mistakes them for results.

What IS real here: the shadow and sun-fraction maths (horizon.py,
sunfrac.py) and the scoring rules (metrics.py) are the same code the real
pipeline will use. Only the inputs are invented.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from sunchaser_data import schema  # noqa: E402
from sunchaser_data.horizon import horizon_profile, interp_horizon  # noqa: E402
from sunchaser_data.metrics import PLACEHOLDER_CRITERIA, window_metrics  # noqa: E402
from sunchaser_data.sunfrac import sun_visible_fraction  # noqa: E402

START = datetime(2027, 2, 1, tzinfo=timezone.utc)
TIMELINE_HOURS = 24 * 7      # one week, as the handoff asks for
GRID_STEPS = 336             # 14 days at 1 hour, matching the real grid
SYNODIC_H = 29.53 * 24       # sunrise-to-sunrise at a lunar site (real figure)
LIBRATION_H = 27.32 * 24     # Earth's bobbing period (real figure, simplified)

FAKE_SITES = [
    # Positions are invented, near the pole, so map markers land sensibly.
    {"id": "site_a", "name": "FAKE Ridge A", "lat": -89.45, "lon": 137.3, "elevation_m": 1850,
     "source": "FAKE DATA for development, not NASA data", "notes": "Fake ridge, mostly lit"},
    {"id": "site_b", "name": "FAKE Plateau B", "lat": -88.80, "lon": 60.0, "elevation_m": 1200,
     "source": "FAKE DATA for development, not NASA data", "notes": "Fake plateau, long dark spells"},
    {"id": "site_c", "name": "FAKE Rim C", "lat": -87.90, "lon": 300.0, "elevation_m": 900,
     "source": "FAKE DATA for development, not NASA data", "notes": "Fake crater rim, Earth often blocked"},
]

# A made-up terrain horizon for each site: a smooth wavy line in degrees.
FAKE_HORIZON_SHAPE = {
    "site_a": [(0.3, 1, 40), (0.2, 3, 10)],
    "site_b": [(0.3, 1, 60), (0.3, 2, 30)],
    "site_c": [(0.6, 1, 120), (1.2, 2, 0)],
}
FAKE_HORIZON_BASE = {"site_a": 0.1, "site_b": 0.2, "site_c": 0.8}


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%MZ")


def fake_sun(hours):
    """FAKE Sun: azimuth turns once per lunar day, elevation wobbles around 0.6 deg."""
    az = np.mod(360.0 * hours / SYNODIC_H, 360.0)
    elev = 0.6 + 0.5 * np.cos(np.radians(az - 90.0))
    return elev, az


# Each fake site starts at a different point in Earth's bobbing cycle (radians),
# so the week shows constant contact at A, a mid-week loss at B, little at C.
FAKE_EARTH_PHASE = {"site_a": 0.3, "site_b": 2.5, "site_c": 4.0}


def fake_earth(hours, site_lon, phase=0.0):
    """FAKE Earth: bobs between about -5.2 and +8.2 deg; sits roughly toward 0 deg longitude."""
    elev = 1.5 + 6.7 * np.sin(2 * np.pi * hours / LIBRATION_H + phase)
    az = np.mod(360.0 - site_lon + 7.0 * np.sin(2 * np.pi * hours / LIBRATION_H), 360.0)
    return elev, az


def fake_horizon_profile(site_id):
    az = np.arange(0.0, 360.0, 0.5)
    prof = np.full_like(az, FAKE_HORIZON_BASE[site_id])
    for amp, k, phase in FAKE_HORIZON_SHAPE[site_id]:
        prof += amp * np.cos(np.radians(k * az - phase))
    return az, prof


def make_timeline(site):
    hours = np.arange(TIMELINE_HOURS, dtype=float)
    sun_elev, sun_az = fake_sun(hours)
    earth_elev, earth_az = fake_earth(hours, site["lon"], FAKE_EARTH_PHASE[site["id"]])
    prof_az, prof = fake_horizon_profile(site["id"])
    sun_hz = interp_horizon(prof, prof_az, sun_az)
    earth_hz = interp_horizon(prof, prof_az, earth_az)
    frac = sun_visible_fraction(sun_elev, sun_hz)
    rows = []
    for i, h in enumerate(hours):
        rows.append({
            "time": iso(START + timedelta(hours=h)),
            "sun_elev_deg": round(float(sun_elev[i]), 2),
            "sun_az_deg": round(float(sun_az[i]), 2) % 360,
            "sun_horizon_deg": round(float(sun_hz[i]), 2),
            "sun_frac": round(float(frac[i]), 2),
            "earth_elev_deg": round(float(earth_elev[i]), 2),
            "earth_az_deg": round(float(earth_az[i]), 2) % 360,
            "earth_horizon_deg": round(float(earth_hz[i]), 2),
            "earth_visible": bool(earth_elev[i] > earth_hz[i]),
            "dsn_station": None,
            "surface_temp_k": None,
        })
    return {"site": site["id"], "start": iso(START), "step_h": 1, "rows": rows}


def make_grid(site, n=64, cell=40.0):
    """FAKE terrain (plain + hills + ridge) with REAL ray-cast shadows."""
    r, c = np.mgrid[0:n, 0:n].astype(float)
    elev = np.full((n, n), float(site["elevation_m"]))
    for hr, hc, height, width_cells in [(18, 40, 70, 9), (44, 18, 90, 11), (46, 48, 50, 7)]:
        elev += height * np.exp(-((r - hr) ** 2 + (c - hc) ** 2) / (2 * width_cells ** 2))
    # A steep ridge across the middle with a gap, so slope limits matter.
    ridge = np.exp(-((r - 0.6 * c - 14) ** 2) / (2 * 1.2 ** 2)) * 60.0
    ridge[(c > 26) & (c < 32)] = 0.0
    elev += ridge

    gr, gc = np.gradient(elev, cell)
    slope = np.degrees(np.arctan(np.hypot(gr, gc)))

    # Per-cell horizon profile in 2-degree bins (real ray casting, fake terrain).
    bins = np.arange(0.0, 360.0, 2.0)
    profiles = np.empty((n, n, bins.size))
    for i in range(n):
        for j in range(n):
            profiles[i, j] = horizon_profile(elev, cell, i, j, bins, step_cells=1.0)

    hours = np.arange(GRID_STEPS, dtype=float)
    sun_elev, sun_az = fake_sun(hours)
    sun_pct = []
    flat = profiles.reshape(-1, bins.size)
    for s in range(GRID_STEPS):
        k = np.interp(sun_az[s], np.append(bins, 360.0), np.arange(bins.size + 1)) % bins.size
        k0 = int(np.floor(k)) % bins.size
        k1 = (k0 + 1) % bins.size
        w = k - np.floor(k)
        hz = flat[:, k0] * (1 - w) + flat[:, k1] * w
        pct = np.rint(100 * sun_visible_fraction(sun_elev[s], hz)).astype(int).reshape(n, n)
        sun_pct.append(pct.tolist())

    return {
        "site": site["id"],
        "window_start": iso(START),
        "step_h": 1,
        "n_steps": GRID_STEPS,
        "rows": n,
        "cols": n,
        "cell_size_m": cell,
        "center": {"lat": site["lat"], "lon": site["lon"]},
        "orientation_note": "FAKE grid. Rows run top to bottom and columns left to right; "
                            "north is up the grid in this fake world.",
        "elevation_m": np.round(elev, 1).tolist(),
        "slope_deg": np.round(slope, 1).tolist(),
        "sun_pct": sun_pct,
    }


def make_scores(timelines):
    rows = []
    for site_id, tl in timelines.items():
        m = window_metrics([x["sun_frac"] for x in tl["rows"]],
                           [x["earth_visible"] for x in tl["rows"]],
                           PLACEHOLDER_CRITERIA)
        rows.append({"site": site_id, **m, "best_landing": tl["start"],
                     "brief": "FAKE DATA: placeholder brief. The real one is written by the AI "
                              "from computed numbers only."})
    rows.sort(key=lambda x: (-x["usable_days"], x["longest_dark_h"], -x["contact_hours"]))
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    ordered = [{k: row[k] for k in ("site", "rank", "usable_days", "sun_hours", "contact_hours",
                                    "both_hours", "longest_dark_h", "survives", "best_landing",
                                    "brief")} for row in rows]
    end = START + timedelta(hours=TIMELINE_HOURS - 1)
    return {"generated": iso(datetime.now(timezone.utc).replace(second=0, microsecond=0)),
            "window_start": START.strftime("%Y-%m-%d"), "window_end": end.strftime("%Y-%m-%d"),
            "sites": ordered}


def write(name, data, check, compact=True):
    errors = check(data)
    if errors:
        raise SystemExit(f"{name} fails the schema:\n  " + "\n  ".join(errors[:10]))
    sep = (",", ":") if compact else None
    text = json.dumps(data, separators=sep, indent=None if compact else 2)
    (HERE / name).write_text(text)
    print(f"  {name:24s} {len(text) / 1024:8.0f} KB  (schema OK)")


def main():
    print("Writing FAKE data to data/fake/ ...")
    write("sites.json", FAKE_SITES, schema.check_sites, compact=False)
    timelines = {s["id"]: make_timeline(s) for s in FAKE_SITES}
    for site_id, tl in timelines.items():
        write(f"timeline_{site_id}.json", tl, schema.check_timeline)
    write("scores.json", make_scores(timelines), schema.check_scores, compact=False)
    print("  computing fake shadow grid (ray casting 4,096 cells)...")
    write("grid_site_a.json", make_grid(FAKE_SITES[0]), schema.check_grid)


if __name__ == "__main__":
    main()
