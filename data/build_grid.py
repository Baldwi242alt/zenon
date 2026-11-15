"""Shadow grids: shared/grid_SITE.json (schema 2.3) for every site.

Run from the repo root:
  python data/build_grid.py --year [--site ID]     # 1. per-cell horizons + a year of sunlight (cache)
  python planner/find_scenarios.py                 # 2. Harril's planner picks each site's demo window
  python data/build_grid.py --from-scenarios       # 3. write shared/grid_SITE.json for those windows
  python data/build_grid.py --site ID --start 2027-MM-DDTHH:00Z   # or write one grid by hand

The grid is 64 x 64 cells of 80 m: a 5.1 km x 5.1 km operations area centred
on the site, 336 hourly steps (14 days).

Why 80 m cells: with 40 m cells (2.56 km across) no crossing takes longer than
about 15 hours, and the reference rover survives about 22 hours of darkness from
a full battery, so no route could ever fail and there was nothing for the
sun-chasing planner to beat. Tested on all 9 sites: the battery never fell below
48%. A 5 km area gives traverses of 25-35 hours, where darkness really can kill.
The rover's specifications were NOT changed to manufacture drama.

Step 1 is the slow part (about a minute per site): a terrain horizon for each of
the 4,096 cells. Its result, plus sun_pct for every hour of 2027, is cached in
data/cache/grids/ so the planner can search the whole year for a window where
the shortest route fails and the sun-chasing route survives (handbook B.11:
"pick a dramatic window with Harril").
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

from sunchaser_data import schema  # noqa: E402
from sunchaser_data.grid import ShadowGrid  # noqa: E402
from sunchaser_data.illumination import load_standard_dems  # noqa: E402

SHARED = ROOT / "shared"
CACHE = ROOT / "data" / "cache" / "grids"
SCENARIOS = ROOT / "planner" / "scenarios.json"
N_STEPS = 336      # 14 days at 1 hour
CELL_M = 80.0
ROWS = COLS = 64
FIELDS = ("elevation", "slope", "horizon", "off_north", "off_east", "az_shift")


def load_timeline(site_id):
    return json.loads((SHARED / f"timeline_{site_id}.json").read_text())


def grid_for(site, dems=None):
    """The ShadowGrid for a site, from the cache or built (about a minute)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{site['id']}_{int(CELL_M)}m.npz"
    if path.exists():
        g = ShadowGrid.__new__(ShadowGrid)
        with np.load(path) as z:
            for k in FIELDS:
                setattr(g, k, z[k])
            g.north_c, g.east_c = tuple(z["north_c"]), tuple(z["east_c"])
        g.rows, g.cols, g.cell = ROWS, COLS, CELL_M
        return g
    near, far = dems if dems else load_standard_dems()
    g = ShadowGrid(near, far, site["lat"], site["lon"], rows=ROWS, cols=COLS, cell_size_m=CELL_M)
    np.savez_compressed(path, north_c=np.array(g.north_c), east_c=np.array(g.east_c),
                        **{k: getattr(g, k) for k in FIELDS})
    return g


def build_year(site, dems=None):
    """Cache sun_pct for every hour of 2027 (used by the planner's scenario search)."""
    g = grid_for(site, dems)
    rows = load_timeline(site["id"])["rows"]
    pct = g.sun_pct([r["sun_az_deg"] for r in rows], [r["sun_elev_deg"] for r in rows]).astype(np.uint8)
    out = CACHE / f"year_{site['id']}.npz"
    np.savez_compressed(out, sun_pct=pct, elevation_m=np.round(g.elevation, 1), slope_deg=np.round(g.slope, 1),
                        cell_size_m=CELL_M, start=rows[0]["time"])
    print(f"  {site['id']:22s} year cache: {100 * (pct >= 50).mean():4.1f}% of cell-hours lit, "
          f"{100 * (g.slope > 15).mean():4.1f}% of cells steeper than 15 deg, "
          f"relief {g.elevation.max() - g.elevation.min():.0f} m")


def write_grid(site, start_time, dems=None):
    g = grid_for(site, dems)
    tl = load_timeline(site["id"])
    times = [r["time"] for r in tl["rows"]]
    i0 = times.index(start_time)
    rows = tl["rows"][i0:i0 + N_STEPS]
    if len(rows) < N_STEPS:
        raise SystemExit(f"{site['id']}: window from {start_time} runs past the end of the timeline")
    pct = g.sun_pct([r["sun_az_deg"] for r in rows], [r["sun_elev_deg"] for r in rows])
    north_deg = np.degrees(np.arctan2(g.north_c[1], -g.north_c[0])) % 360
    grid = {
        "site": site["id"],
        "window_start": start_time,
        "step_h": 1,
        "n_steps": N_STEPS,
        "rows": ROWS,
        "cols": COLS,
        "cell_size_m": CELL_M,
        "center": {"lat": site["lat"], "lon": site["lon"]},
        "orientation_note": "Rows run top to bottom and columns left to right, matching the "
                            "south-polar map image (LOLA polar stereographic); 0° longitude points up. "
                            f"Local north at this site points {north_deg:.0f}° clockwise from the top of the grid.",
        "elevation_m": np.round(g.elevation, 1).tolist(),
        "slope_deg": np.round(g.slope, 1).tolist(),
        "sun_pct": pct.astype(int).tolist(),
    }
    errors = schema.check_grid(grid)
    if errors:
        raise SystemExit("grid fails the schema:\n  " + "\n  ".join(errors[:10]))
    out = SHARED / f"grid_{site['id']}.json"
    out.write_text(json.dumps(grid, separators=(",", ":")))
    lit = pct >= 50
    print(f"  {out.name:32s} from {start_time}  {out.stat().st_size / 1e6:.1f} MB  "
          f"{lit.mean() * 100:.0f}% of cell-hours lit (first day {lit[:24].mean() * 100:.0f}%, "
          f"last day {lit[-24:].mean() * 100:.0f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", action="store_true", help="build per-cell horizons and the 2027 sunlight cache")
    ap.add_argument("--from-scenarios", action="store_true", help="write grids for the windows in planner/scenarios.json")
    ap.add_argument("--site")
    ap.add_argument("--start")
    args = ap.parse_args()
    sites = json.loads((SHARED / "sites.json").read_text())
    chosen = [s for s in sites if not args.site or s["id"] == args.site]
    if args.year:
        need_dems = any(not (CACHE / f"{s['id']}_{int(CELL_M)}m.npz").exists() for s in chosen)
        dems = load_standard_dems() if need_dems else None
        for s in chosen:
            build_year(s, dems)
    if args.from_scenarios:
        scenarios = json.loads(SCENARIOS.read_text())
        for s in chosen:
            write_grid(s, scenarios[s["id"]]["window_start"])
    if args.site and args.start:
        write_grid(chosen[0], args.start)


if __name__ == "__main__":
    main()
