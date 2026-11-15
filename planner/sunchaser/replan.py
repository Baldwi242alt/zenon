"""Replanning demo: something goes wrong halfway, and the rover adapts.

Scenario: part-way along the planned route, dust settles on the solar panel and
its output drops (by 30% by default). Two things can happen next:
  - keep following the original plan with the weaker panel, or
  - replan from the rover's current cell, time and battery level, knowing the
    panel is weaker.
replan_after_fault() computes both so they can be compared.
"""

from .astar_st import plan_route
from .sim import simulate


def replan_after_fault(world, plan, depart_step, target, at_fraction=0.5, panel_scale=0.7, change_soon=None):
    """Returns a dict describing the fault and both outcomes, or None if the plan is too short."""
    if len(plan) < 4:
        return None
    k = max(1, int(len(plan) * at_fraction))            # the fault happens after step k
    before = simulate(world, plan[:k + 1], depart_step)
    here = (plan[k][1], plan[k][2])
    t_fault = before["duration_h"]
    energy = before["final_energy_wh"]

    rest = [("start", here[0], here[1], 0.0)] + list(plan[k + 1:])
    original = simulate(world, rest, depart_step, panel_scale=panel_scale, start_energy=energy, start_t=t_fault)
    new_plan, stats = plan_route(world, here, target, depart_step, start_energy=energy, start_t=t_fault,
                                 panel_scale=panel_scale, change_soon=change_soon)
    replanned = None
    if new_plan is not None:
        replanned = simulate(world, new_plan, depart_step, panel_scale=panel_scale,
                             start_energy=energy, start_t=t_fault)
    return {
        "fault": f"panel output x{panel_scale:g} from t = {t_fault:.1f} h",
        "fault_at": {"t_h": round(t_fault, 2), "row": here[0], "col": here[1], "battery_wh": round(energy, 1)},
        "original_plan_after_fault": _summary(original, world),
        "replanned": _summary(replanned, world) if replanned else None,
        "replanned_steps": replanned["steps"] if replanned else [],
        "original_steps_after_fault": original["steps"],
    }


def _summary(r, world):
    return {"survived": r["survived"], "reserve_kept": not r["reserve_breached"],
            "arrival_t_h": r["steps"][-1]["t_h"], "min_battery_pct": r["min_battery_pct"],
            "distance_m": r["distance_m"]}
