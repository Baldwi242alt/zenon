"""Fast versus safe: the trade-off between arriving early and arriving with margin.

The space-time planner keeps the battery above a reserve. A small reserve lets
the rover push on through marginal conditions and arrive sooner; a large one
makes it wait and detour more, arriving later but with far more energy in hand
if something goes wrong. Planning the same trip at several reserve levels and
measuring each route's survival probability gives a mission team the menu:
"this much time buys this much safety".
"""

from .astar_st import plan_route
from .montecarlo import survival_probability
from .sim import simulate


def pareto_routes(world, start, target, depart_step, reserves=None, runs=500, change_soon=None):
    """Plan at each reserve level. Returns a list of dicts (one per level that has a route):
    {"reserve_pct", "plan", "result" (simulate output), "mc" (Monte Carlo output)}.
    """
    if reserves is None:
        reserves = [world.min_soc, 0.30, 0.45]
    out = []
    for frac in sorted(set(round(r, 4) for r in reserves)):
        plan, stats = plan_route(world, start, target, depart_step, reserve_frac=frac, change_soon=change_soon)
        if plan is None:
            continue
        out.append({"reserve_pct": round(100 * frac, 1), "plan": plan,
                    "result": simulate(world, plan, depart_step),
                    "mc": survival_probability(world, plan, depart_step, n=runs), "stats": stats})
    return out
