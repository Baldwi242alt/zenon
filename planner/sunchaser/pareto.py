"""Fast versus safe: the trade-off between arriving early and arriving with margin.

The space-time planner keeps the battery above a reserve. A small reserve lets
the rover push on through marginal conditions and arrive sooner; a large one
makes it wait and detour more, arriving later but with far more energy in hand
if something goes wrong. Planning the same trip at several reserve levels and
measuring each route's survival probability gives a mission team the menu:
"this much time buys this much safety".
"""

import time

from .astar_st import plan_route
from .montecarlo import survival_probability
from .sim import simulate


EXTRA_LEVEL_LABELS = 250_000   # search budget for the higher reserves (a route may simply not exist)


def pareto_routes(world, start, target, depart_step, reserves=None, runs=500, change_soon=None, log=None):
    """Plan at each reserve level. Returns a list of dicts (one per level that has a route):
    {"reserve_pct", "plan", "result" (simulate output), "mc" (Monte Carlo output)}.
    """
    if reserves is None:
        reserves = [world.min_soc, 0.30, 0.45]
    out = []
    for i, frac in enumerate(sorted(set(round(r, 4) for r in reserves))):
        # The first (lowest) reserve gets the full search budget. Higher reserves are optional
        # extras: if no such route exists the search would otherwise run through every reachable
        # state in the 14-day window, so it is capped.
        budget = {} if i == 0 else {"max_labels": EXTRA_LEVEL_LABELS, "max_seconds": 60.0}
        t0 = time.time()
        plan, stats = plan_route(world, start, target, depart_step, reserve_frac=frac, change_soon=change_soon,
                                 **budget)
        if log:
            log(f"   reserve {100 * frac:.0f}%: {stats['reason']}, {stats['labels']:,} labels, {time.time() - t0:.0f} s")
        if plan is None:
            continue
        out.append({"reserve_pct": round(100 * frac, 1), "plan": plan,
                    "result": simulate(world, plan, depart_step),
                    "mc": survival_probability(world, plan, depart_step, n=runs), "stats": stats})
    return out
