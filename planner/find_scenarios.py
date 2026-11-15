"""Find each site's demo scenario: where and when does the naive route fail and Sunchaser survive?

Run from the repo root (after `python data/build_grid.py --year`):
    python planner/find_scenarios.py [--site ID]

For every site this searches the whole of 2027 (handbook 5.10, "find a dramatic
scenario"):
  1. Candidate start/target pairs: gentle, drivable cells on a 5 x 5 lattice across
     the 5.1 km grid, at least 3.8 km apart.
  2. For each pair, the shortest route is found once, then replayed for a departure
     every 12 hours of the year. Departures are kept when the rover starts in
     sunlight (it had a chance to charge) and the shortest route FREEZES.
  3. The most promising of those are handed to the space-time planner, on a 14-day
     window that starts one day before departure. Both routes get a Monte Carlo
     survival probability.
  4. The scenario kept is the one with the biggest gap between Sunchaser's and the
     shortest route's survival probability, preferring shorter Sunchaser trips.

If the shortest route never freezes at a site (or Sunchaser can't save it), the
site's scenario is the one where the shortest route cuts deepest into its
battery, and the note says so. Nothing is staged: every scenario is a real
window of 2027 with the rover's specifications unchanged.

Output: planner/scenarios.json, read by data/build_grid.py (which window to
write to shared/grid_SITE.json) and by planner/run.py (start, target, departure).
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "planner"))

from sunchaser.astar2d import shortest_path  # noqa: E402
from sunchaser.astar_st import change_soon_table, plan_route  # noqa: E402
from sunchaser.io import SHARED, load_rover  # noqa: E402
from sunchaser.montecarlo import survival_probability  # noqa: E402
from sunchaser.sim import path_to_plan, simulate  # noqa: E402
from sunchaser.world import World  # noqa: E402

CACHE = ROOT / "data" / "cache" / "grids"
OUT = ROOT / "planner" / "scenarios.json"
WINDOW_H = 336
LEAD_H = 24                 # the window starts this long before departure
LATTICE = [5, 18, 32, 45, 58]
MIN_SEPARATION_M = 3800.0
DEPART_EVERY_H = 12
SHORTLIST = 24
SEARCH_LABELS = 80_000    # give up on a candidate after this many labels (hopeless cases are slow)
MC_RUNS = 200


def load_year(site_id):
    z = np.load(CACHE / f"year_{site_id}.npz")
    return {"sun": z["sun_pct"], "elev": z["elevation_m"], "slope": z["slope_deg"],
            "cell": float(z["cell_size_m"]), "start": str(z["start"])}


def as_grid(year, s0, n):
    sun = year["sun"][s0:s0 + n]
    return {"rows": sun.shape[1], "cols": sun.shape[2], "cell_size_m": year["cell"], "n_steps": sun.shape[0],
            "elevation_m": year["elev"].tolist(), "slope_deg": year["slope"].tolist(), "sun_pct": sun.tolist()}


def endpoints(world, gentle_deg=8.0):
    """Lattice points snapped to the nearest gentle, drivable cell."""
    pts = []
    for r0 in LATTICE:
        for c0 in LATTICE:
            best = None
            for dr in range(-5, 6):
                for dc in range(-5, 6):
                    r, c = r0 + dr, c0 + dc
                    if 2 <= r < world.rows - 2 and 2 <= c < world.cols - 2 and world.drivable(r, c) \
                            and world.slope[world.idx(r, c)] <= gentle_deg:
                        d = dr * dr + dc * dc
                        if best is None or d < best[0]:
                            best = (d, (r, c))
            if best and best[1] not in pts:
                pts.append(best[1])
    return pts


def iso(start, hours):
    t = datetime.strptime(start, "%Y-%m-%dT%H:%MZ") + timedelta(hours=int(hours))
    return t.strftime("%Y-%m-%dT%H:%MZ")


def search_site(site_id, rover, log=print):
    t_begin = time.time()
    year = load_year(site_id)
    n_year = year["sun"].shape[0]
    world = World(as_grid(year, 0, n_year), rover)
    pts = endpoints(world)
    pairs = []
    for a in pts:
        for b in pts:
            if a != b and world.octile_m(world.idx(*a), world.idx(*b)) >= MIN_SEPARATION_M:
                path = shortest_path(world, a, b)
                if path:
                    pairs.append((a, b, path_to_plan(world, path)))
    log(f"{site_id}: {len(pts)} endpoints, {len(pairs)} start/target pairs")

    # --- screen the year with the shortest route ---
    frozen, deepest = [], []
    lit_share = (year["sun"] >= 50).reshape(n_year, -1).mean(axis=1)
    for dep in range(LEAD_H, n_year - WINDOW_H + LEAD_H, DEPART_EVERY_H):
        for a, b, plan in pairs:
            if world.sun[dep][world.idx(*a)] < 80:
                continue
            r = simulate(world, plan, dep, log=False)
            item = (dep, a, b, r["min_battery_pct"], r["duration_h"], float(lit_share[dep:dep + 72].mean()))
            if not r["survived"]:
                frozen.append(item)
            elif r["reserve_breached"]:
                deepest.append(item)
    log(f"{site_id}: shortest route freezes in {len(frozen)} cases, breaches the reserve in {len(deepest)} more "
        f"({time.time() - t_begin:.0f} s)")

    def shortlist(items, key):
        """Spread the shortlist over different departures so we don't test one week 36 times."""
        picked, used = [], {}
        for it in sorted(items, key=key):
            week = it[0] // 168
            if used.get(week, 0) >= 3:
                continue
            used[week] = used.get(week, 0) + 1
            picked.append(it)
            if len(picked) >= SHORTLIST:
                break
        return picked

    def evaluate(items, froze):
        best = None
        for dep, a, b, _, _, _ in items:
            s0 = dep - LEAD_H
            w = World(as_grid(year, s0, WINDOW_H), rover)
            cs = change_soon_table(w)
            plan, stats = plan_route(w, a, b, LEAD_H, change_soon=cs, max_labels=SEARCH_LABELS)
            if plan is None:
                continue
            naive = path_to_plan(w, shortest_path(w, a, b))
            smart = simulate(w, plan, LEAD_H, log=False)
            p_smart = survival_probability(w, plan, LEAD_H, n=MC_RUNS)["survival_probability"]
            p_naive = survival_probability(w, naive, LEAD_H, n=MC_RUNS)["survival_probability"]
            waits = sum(1 for s in plan if s[0] == "wait")
            # Biggest survival gap first; shorter trips preferred; a small bonus when the
            # rover really does park in sunlight to let a shadow pass (the story we tell).
            score = (p_smart - p_naive) - 0.003 * smart["duration_h"] + (0.05 if waits else 0.0)
            cand = {"window_start": iso(year["start"], s0), "depart_step": LEAD_H,
                    "start": {"row": a[0], "col": a[1]}, "target": {"row": b[0], "col": b[1]},
                    "shortest_freezes": froze, "search": {
                        "sunchaser_duration_h": smart["duration_h"], "sunchaser_min_battery_pct": smart["min_battery_pct"],
                        "sunchaser_survival_probability": p_smart, "shortest_survival_probability": p_naive,
                        "waits": waits, "score": round(score, 3)}}
            if best is None or score > best["search"]["score"]:
                best = cand
        return best

    # Most light around departure first: those are the cases Sunchaser can most likely rescue.
    best = evaluate(shortlist(frozen, key=lambda it: (-it[5], it[3])), True)
    if best is None:
        best = evaluate(shortlist(deepest, key=lambda it: it[3]), False)
    if best is None:
        log(f"{site_id}: no scenario found")
        return None
    best["note"] = ("Shortest route freezes; Sunchaser survives." if best["shortest_freezes"] else
                    "The shortest route never freezes on a rescuable trip at this site in 2027; this is the trip "
                    "where it cuts deepest into the battery reserve.")
    s = best["search"]
    log(f"{site_id}: window {best['window_start']}  {best['start']} -> {best['target']}  "
        f"shortest p_survive {s['shortest_survival_probability']:.2f} | sunchaser {s['sunchaser_duration_h']:.1f} h, "
        f"p_survive {s['sunchaser_survival_probability']:.2f}, {s['waits']} waits  ({time.time() - t_begin:.0f} s)")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", help="one site id, or several separated by commas (default: all)")
    ap.add_argument("--merge-only", action="store_true", help="just rebuild scenarios.json from finished searches")
    args = ap.parse_args()
    rover, source = load_rover()
    print(f"Rover: {source}", flush=True)
    sites = [s["id"] for s in json.loads((SHARED / "sites.json").read_text())]
    wanted = args.site.split(",") if args.site else sites
    for sid in sites:
        if args.merge_only or sid not in wanted:
            continue
        if not (CACHE / f"year_{sid}.npz").exists():
            print(f"{sid}: no year cache (run data/build_grid.py --year)")
            continue
        found = search_site(sid, rover, log=lambda m: print(m, flush=True))
        if found:
            # One file per site, so several searches can run side by side.
            (CACHE / f"scenario_{sid}.json").write_text(json.dumps(found))
    done = {sid: json.loads((CACHE / f"scenario_{sid}.json").read_text())
            for sid in sites if (CACHE / f"scenario_{sid}.json").exists()}
    OUT.write_text(json.dumps(done, indent=1) + "\n")
    print(f"planner/scenarios.json now has {len(done)} of {len(sites)} sites")


if __name__ == "__main__":
    main()
