"""Plan every route for a site and write shared/route_SITE.json (schema 2.8).

Run from the repo root:
    python planner/run.py --all
    python planner/run.py --site slater_plain
    python planner/run.py --site slater_plain --start 6,6 --target 55,50 --depart 24

For each site:
  1. load the rover (shared/rover.json, or the placeholder) and shared/grid_SITE.json;
  2. take start, target and departure from planner/scenarios.json (written by
     find_scenarios.py), or from the command line, or pick them automatically;
  3. plan the naive `shortest` route (2D A*, ignores the Sun) and replay it;
  4. plan Sunchaser routes with the space-time planner at three battery reserves
     (the rover's own reserve, 30% and 45%): the first is `sunchaser_fast`, the
     highest that still reaches the target is `sunchaser_safe`, and all three
     form the `pareto` list (time versus survival probability);
  5. give every route a Monte Carlo survival probability (500 runs);
  6. run the replanning demo (panel output drops 30% part-way) and save it to
     planner/out/replan_SITE.json;
  7. check the result against the schema and the handbook's self-checks, and
     write shared/route_SITE.json.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "planner"))

from sunchaser.astar2d import shortest_path  # noqa: E402
from sunchaser.astar_st import change_soon_table  # noqa: E402
from sunchaser.io import SHARED, check_route_file, load_grid, load_rover, route_entry  # noqa: E402
from sunchaser.montecarlo import survival_probability  # noqa: E402
from sunchaser.pareto import pareto_routes  # noqa: E402
from sunchaser.replan import replan_after_fault  # noqa: E402
from sunchaser.sim import path_to_plan, simulate  # noqa: E402
from sunchaser.world import World  # noqa: E402

SCENARIOS = ROOT / "planner" / "scenarios.json"
OUT_DIR = ROOT / "planner" / "out"
MC_RUNS = 500


def auto_endpoints(world, depart_step):
    """Gentle, sunlit cells near opposite corners, at least 2 km apart (handbook 5.10)."""
    def pick(r0, c0):
        best = None
        for r in range(world.rows):
            for c in range(world.cols):
                i = world.idx(r, c)
                if world.drivable(r, c) and world.slope[i] <= 8 and world.sun[depart_step][i] >= 80:
                    d = (r - r0) ** 2 + (c - c0) ** 2
                    if best is None or d < best[0]:
                        best = (d, (r, c))
        return best[1] if best else None

    m = 5
    corners = [((m, m), (world.rows - 1 - m, world.cols - 1 - m)),
               ((world.rows - 1 - m, m), (m, world.cols - 1 - m))]
    for a0, b0 in corners:
        a, b = pick(*a0), pick(*b0)
        if a and b and world.octile_m(world.idx(*a), world.idx(*b)) >= 2000 and shortest_path(world, a, b):
            return a, b
    raise SystemExit("could not find a sunlit, gentle start and target at least 2 km apart")


def plan_site(site, rover, start=None, target=None, depart=None, log=print):
    t_begin = time.time()
    grid = load_grid(site)
    world = World(grid, rover)
    scen = json.loads(SCENARIOS.read_text()).get(site) if SCENARIOS.exists() else None
    if scen and scen["window_start"] != grid["window_start"]:
        log(f"  note: planner/scenarios.json is for a different window than shared/grid_{site}.json; ignoring it")
        scen = None
    if depart is None:
        depart = scen["depart_step"] if scen else 0
    if start is None or target is None:
        if scen:
            start = (scen["start"]["row"], scen["start"]["col"])
            target = (scen["target"]["row"], scen["target"]["col"])
        else:
            start, target = auto_endpoints(world, depart)
    cs = change_soon_table(world)

    path = shortest_path(world, start, target)
    if path is None:
        raise SystemExit(f"{site}: no drivable route from {start} to {target}")
    naive_plan = path_to_plan(world, path)
    naive = simulate(world, naive_plan, depart)
    naive_mc = survival_probability(world, naive_plan, depart, n=MC_RUNS)
    routes = [route_entry("shortest", naive, naive_mc)]

    levels = pareto_routes(world, start, target, depart, runs=MC_RUNS, change_soon=cs, log=log)
    pareto = []
    if levels:
        fast = levels[0]
        routes.append(route_entry("sunchaser_fast", fast["result"], fast["mc"]))
        if len(levels) > 1:
            # "Max margin": the route with the best survival odds (ties go to the bigger reserve).
            safe = max(levels[1:], key=lambda p: (p["mc"]["survival_probability"], p["reserve_pct"]))
            same = safe["result"]["steps"] == fast["result"]["steps"]     # no safer route exists: don't list it twice
            if not same and safe["mc"]["survival_probability"] >= fast["mc"]["survival_probability"]:
                routes.append(route_entry("sunchaser_safe", safe["result"], safe["mc"]))
        pareto = [{"reserve_pct": p["reserve_pct"], "duration_h": p["result"]["duration_h"],
                   "survival_probability": round(p["mc"]["survival_probability"], 3)} for p in levels]

    data = {"site": site, "start": {"row": start[0], "col": start[1]},
            "target": {"row": target[0], "col": target[1]}, "depart_step": depart,
            "monte_carlo_runs": MC_RUNS, "routes": routes}
    if pareto:
        data["pareto"] = pareto

    errors = check_route_file(data, world)
    if errors:
        raise SystemExit(f"{site}: route file fails its checks:\n  " + "\n  ".join(errors[:12]))
    out = SHARED / f"route_{site}.json"
    out.write_text(json.dumps(data, separators=(",", ":")))

    # Replanning demo (not part of the shared schema; saved next to the planner).
    if levels:
        demo = replan_after_fault(world, levels[0]["plan"], depart, target, change_soon=cs)
        if demo:
            OUT_DIR.mkdir(exist_ok=True)
            (OUT_DIR / f"replan_{site}.json").write_text(json.dumps({"site": site, **demo}, separators=(",", ":")))

    def line(r):
        if r["survived"]:
            return (f"{r['name']}: {r['duration_h']:.1f} h, {r['distance_m'] / 1000:.2f} km, min battery "
                    f"{r['min_battery_pct']:.0f}%, p_survive {r['survival_probability']:.2f}")
        return (f"{r['name']}: FROZE at {r['duration_h']:.1f} h after {r['distance_m'] / 1000:.2f} km "
                f"(p_survive {r['survival_probability']:.2f})")

    log(f"{site}: {start} -> {target}, depart step {depart}  [{time.time() - t_begin:.0f} s, {out.stat().st_size / 1e3:.0f} KB]")
    for r in routes:
        log("   " + line(r))
    if not levels:
        log("   no safe Sunchaser route exists in this window")
    return data


def _plan_quietly(site, rover):
    lines = []
    try:
        plan_site(site, rover, log=lines.append)
    except SystemExit as exc:
        lines.append(f"{site}: FAILED: {exc}")
    return lines


def parse_rc(text):
    r, c = text.split(",")
    return int(r), int(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--start", type=parse_rc, help="row,col")
    ap.add_argument("--target", type=parse_rc, help="row,col")
    ap.add_argument("--depart", type=int, help="hour index in the grid when the rover leaves")
    ap.add_argument("--jobs", type=int, default=3, help="sites planned in parallel with --all")
    args = ap.parse_args()
    rover, source = load_rover()
    print(f"Rover: {source}")
    if args.all:
        sites = [s["id"] for s in json.loads((SHARED / "sites.json").read_text())
                 if (SHARED / f"grid_{s['id']}.json").exists()]
    elif args.site:
        sites = [args.site]
    else:
        ap.error("give --site ID or --all")
    if len(sites) > 1 and args.jobs > 1:
        # Sites are independent, so plan them side by side. Each worker collects its own
        # log lines and they are printed when that site finishes.
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(_plan_quietly, site, rover): site for site in sites}
            for fut in as_completed(futures):
                print("\n".join(fut.result()), flush=True)
    else:
        for site in sites:
            plan_site(site, rover, args.start, args.target, args.depart)


if __name__ == "__main__":
    main()
