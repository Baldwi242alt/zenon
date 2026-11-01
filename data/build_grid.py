"""Stage 6: shadow grid (shared/grid_SITE.json) for the demo site.

Run from the repo root:
  python data/build_grid.py --scan            # rank sites/windows for a dramatic demo
  python data/build_grid.py --site ID --start 2027-MM-DDTHH:00Z   # write one grid
  python data/build_grid.py --all             # every site, at its best window from the scan

Choosing the window (handbook B.11): the demo needs a 14-day window where
shadows sweep across the grid, so that some cells stay dark longer than the
rover can survive while others stay lit. Then the naive shortest route can
freeze and the Sunchaser route can survive. --scan scores every daily start
in 2027 at every site:

  sweep    share of cells that are lit 20-80% of the window (shadows move)
  deadly   share of cells whose longest dark spell exceeds the survivable
           limit (max_dark_spell_hours from criteria; placeholder 18 h)
  start    share of cells lit at the first hour (somewhere to start from)
  score  = sweep x (1 - 2 |deadly - 0.5|) x start

The top options are written to data/sites/grid_window_options.csv so
Harril can pick together with us.
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

from sunchaser_data import schema  # noqa: E402
from sunchaser_data.grid import ShadowGrid  # noqa: E402
from sunchaser_data.illumination import load_standard_dems  # noqa: E402
from sunchaser_data.metrics import PLACEHOLDER_CRITERIA  # noqa: E402

SHARED = ROOT / "shared"
CACHE = ROOT / "data" / "cache" / "grids"
OPTIONS_OUT = ROOT / "data" / "sites" / "grid_window_options.csv"
N_STEPS = 336  # 14 days at 1 hour


def load_criteria():
    path = SHARED / "criteria.json"
    if path.exists():
        return json.loads(path.read_text()), "shared/criteria.json"
    return PLACEHOLDER_CRITERIA, "placeholder criteria (shared/criteria.json not committed yet)"


def load_timeline(site_id):
    return json.loads((SHARED / f"timeline_{site_id}.json").read_text())


def grid_for(site, near, far):
    """Build (or load from cache) the ShadowGrid for a site."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{site['id']}.npz"
    g = None
    if path.exists():
        g = ShadowGrid.__new__(ShadowGrid)
        with np.load(path) as z:
            for k in z.files:
                setattr(g, k, z[k])
        g.rows, g.cols, g.cell = int(g.rows), int(g.cols), float(g.cell)
        g.north_c, g.east_c = tuple(g.north_c), tuple(g.east_c)
        return g
    g = ShadowGrid(near, far, site["lat"], site["lon"])
    np.savez_compressed(path, elevation=g.elevation, slope=g.slope, horizon=g.horizon,
                        off_north=g.off_north, off_east=g.off_east, rows=g.rows, cols=g.cols,
                        cell=g.cell, north_c=np.array(g.north_c), east_c=np.array(g.east_c),
                        lat=g.lat, lon=g.lon, mast=g.mast)
    return g


def longest_run_cells(dark):
    """Longest run of True along axis 0 for every cell. dark: (steps, cells) bool."""
    best = np.zeros(dark.shape[1], dtype=int)
    cur = np.zeros(dark.shape[1], dtype=int)
    for row in dark:
        cur = np.where(row, cur + 1, 0)
        np.maximum(best, cur, out=best)
    return best


def scan(sites, near, far, limit_h):
    options = []
    for site in sites:
        g = grid_for(site, near, far)
        tl = load_timeline(site["id"])
        az = np.array([r["sun_az_deg"] for r in tl["rows"]])
        el = np.array([r["sun_elev_deg"] for r in tl["rows"]])
        lit = (g.sun_pct(az, el) >= 50).reshape(len(az), -1)[:, ::4]   # every 4th cell
        for start in range(0, len(az) - N_STEPS, 24):
            w = lit[start:start + N_STEPS]
            share = w.mean(axis=0)
            sweep = float(((share >= 0.2) & (share <= 0.8)).mean())
            deadly = float((longest_run_cells(~w) > limit_h).mean())
            start_lit = float(w[0].mean())
            score = sweep * (1 - 2 * abs(deadly - 0.5)) * start_lit
            options.append({"site": site["id"], "window_start": tl["rows"][start]["time"],
                            "score": round(score, 3), "sweep": round(sweep, 2),
                            "deadly": round(deadly, 2), "start_lit": round(start_lit, 2),
                            "mean_lit": round(float(w.mean()), 2)})
        best = max(o["score"] for o in options if o["site"] == site["id"])
        print(f"  {site['id']:22s} best window score {best:.3f}")
    options.sort(key=lambda o: -o["score"])
    # Keep the best window per site, then the overall top 10.
    top, seen = [], set()
    for o in options:
        if o["site"] not in seen:
            top.append(o)
            seen.add(o["site"])
    with OPTIONS_OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(options[0].keys()))
        w.writeheader()
        w.writerows(top + [o for o in options[:10] if o not in top])
    return top


def write_grid(site, near, far, start_time):
    g = grid_for(site, near, far)
    tl = load_timeline(site["id"])
    times = [r["time"] for r in tl["rows"]]
    i0 = times.index(start_time)
    rows = tl["rows"][i0:i0 + N_STEPS]
    if len(rows) < N_STEPS:
        raise SystemExit("window runs past the end of the timeline")
    pct = g.sun_pct([r["sun_az_deg"] for r in rows], [r["sun_elev_deg"] for r in rows])
    grid = {
        "site": site["id"],
        "window_start": start_time,
        "step_h": 1,
        "n_steps": N_STEPS,
        "rows": int(g.rows),
        "cols": int(g.cols),
        "cell_size_m": float(g.cell),
        "center": {"lat": site["lat"], "lon": site["lon"]},
        "orientation_note": "Rows run top to bottom and columns left to right, matching the "
                            "south-polar map image (LOLA polar stereographic); 0° longitude points up. "
                            "Local north at this site points "
                            f"{np.degrees(np.arctan2(g.north_c[1], -g.north_c[0])) % 360:.0f}° clockwise "
                            "from the top of the grid.",
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
    print(f"Wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB, schema OK): "
          f"{lit.mean() * 100:.0f}% of cell-hours lit, "
          f"{(g.slope > 15).mean() * 100:.0f}% of cells steeper than 15°")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--site")
    ap.add_argument("--start")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    sites = json.loads((SHARED / "sites.json").read_text())
    criteria, source = load_criteria()
    near, far = load_standard_dems()
    if args.scan:
        print(f"Scanning 2027 for dramatic 14-day windows (dark limit "
              f"{criteria['max_dark_spell_hours']} h from {source})...")
        top = scan(sites, near, far, criteria["max_dark_spell_hours"])
        print("Best window per site:")
        for o in top:
            print(f"  {o['site']:22s} {o['window_start']}  score {o['score']:.3f}  sweep {o['sweep']:.2f}  "
                  f"deadly {o['deadly']:.2f}  lit at start {o['start_lit']:.2f}  mean lit {o['mean_lit']:.2f}")
    if args.site:
        site = next(s for s in sites if s["id"] == args.site)
        write_grid(site, near, far, args.start)
    if args.all:
        if not OPTIONS_OUT.exists():
            raise SystemExit("run --scan first")
        best = {}
        with OPTIONS_OUT.open() as f:
            for row in csv.DictReader(f):
                best.setdefault(row["site"], row["window_start"])  # first row per site = its best
        for site in sites:
            print(f"{site['id']}: window from {best[site['id']]}")
            write_grid(site, near, far, best[site["id"]])


if __name__ == "__main__":
    main()
