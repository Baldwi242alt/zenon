"""Replay a planned route through time and report what happens to the battery.

A plan is a list of actions:
    ("start", row, col, 0.0)        where the rover begins (full battery)
    ("move",  row, col, duration_h) drive to this neighbouring cell
    ("wait",  row, col, duration_h) stay parked in this cell

simulate() walks the plan with World.advance / World.move_energy (the same
energy rules the planner uses) and returns the route in the shape of schema 2.8.

The optional scale factors and delay are for Monte Carlo runs: the same plan
replayed by a rover whose battery, panel and power draw differ a little from
the spec sheet, leaving a little late.
"""

from .world import World


def path_to_plan(world, path):
    """Turn a list of (row, col) cells into a plan that drives without stopping."""
    plan = [("start", path[0][0], path[0][1], 0.0)]
    for (r0, c0), (r1, c1) in zip(path, path[1:]):
        dur = world.diag_h if (r0 != r1 and c0 != c1) else world.side_h
        plan.append(("move", r1, c1, dur))
    return plan


def simulate(world, plan, depart_step, delay_h=0.0, cap_scale=1.0, panel_scale=1.0, draw_scale=1.0,
             log=True, start_energy=None, start_t=0.0):
    """Replay a plan. Returns a dict with the schema-2.8 route fields plus:
      reserve_breached  the battery dipped below the safety reserve at some point
      out_of_window     the plan ran past the end of the grid's time window
      final_energy_wh   battery at the end
    start_energy / start_t let a replay begin part-way through a route (used
    by the replanning demo); by default the rover starts full at t = 0.
    """
    cap = world.cap * cap_scale
    energy = cap if start_energy is None else start_energy
    lowest = energy
    t = start_t
    t0 = depart_step + delay_h
    distance = 0.0
    used = 0.0            # energy drawn by the rover (integral of power out)
    frozen_at = None
    steps = []

    _, r, c, _ = plan[0]
    here = world.idx(r, c)
    if log:
        pct, p_in, p_out = world.powers(here, t0 + t, 0.0, panel_scale, draw_scale)
        steps.append({"t_h": round(t, 3), "row": r, "col": c, "action": "start", "sun_pct": int(pct),
                      "power_in_w": round(p_in, 1), "power_out_w": round(p_out, 1),
                      "battery_wh": round(energy, 1)})

    for action, r, c, dur in plan[1:]:
        there = world.idx(r, c)
        if action == "move":
            move = next((m for m in world.moves[here] if m[0] == there), None)
            if move is None:
                raise ValueError(f"plan moves between cells that are not joined by an allowed move: "
                                 f"{world.rc(here)} -> {(r, c)}")
            drive, dist = move[2], move[3]
            energy, low, froze = world.move_energy(here, there, dur, drive, t0 + t, energy, cap,
                                                   panel_scale, draw_scale)
            ran = dur if froze is None else froze          # hours actually driven
            used += _energy_out(world, here, t0 + t, min(ran, dur / 2), drive, draw_scale)
            if ran > dur / 2:
                used += _energy_out(world, there, t0 + t + dur / 2, ran - dur / 2, drive, draw_scale)
            distance += dist * (ran / dur)
        elif action == "wait":
            if there != here:
                raise ValueError("a wait step must stay in the same cell")
            drive = 0.0
            energy, low, froze = world.advance(here, t0 + t, dur, energy, 0.0, cap, panel_scale, draw_scale)
            used += _energy_out(world, here, t0 + t, dur if froze is None else froze, 0.0, draw_scale)
        else:
            raise ValueError(f"unknown action {action!r}")

        lowest = min(lowest, low)
        t += dur if froze is None else froze
        here = there
        if log:
            pct, p_in, p_out = world.powers(here, t0 + t - 1e-9, drive, panel_scale, draw_scale)
            steps.append({"t_h": round(t, 3), "row": r, "col": c, "action": action, "sun_pct": int(pct),
                          "power_in_w": round(p_in, 1), "power_out_w": round(p_out, 1),
                          "battery_wh": round(max(energy, 0.0), 1)})
        if froze is not None:
            frozen_at = len(steps) - 1 if log else -1
            break

    return {
        "survived": frozen_at is None,
        "frozen_at_index": frozen_at,
        "distance_m": round(distance, 1),
        "duration_h": round(t - start_t, 2),
        "energy_used_wh": round(used, 1),
        "min_battery_pct": round(100.0 * max(lowest, 0.0) / cap, 1),
        "steps": steps,
        "reserve_breached": lowest < world.min_soc * cap - 1e-6,
        "out_of_window": t0 + t > world.n_steps + 1e-9,
        "final_energy_wh": max(energy, 0.0),
    }


def _energy_out(world, idx, t_abs, dt, drive, draw_scale):
    """Energy the rover draws over dt hours in one cell (Wh), split at hour boundaries."""
    total, t, end = 0.0, t_abs, t_abs + dt
    while t < end - 1e-12:
        seg_end = min(int(t) + 1.0, end)
        _, _, p_out = world.powers(idx, t, drive, 1.0, draw_scale)
        total += p_out * (seg_end - t)
        t = seg_end
    return total


def simulate_route(rover, grid, depart_step, path):
    """Harril's original entry point: simulate driving a list of (row, col) cells non-stop."""
    world = World(grid, rover)
    return simulate(world, path_to_plan(world, path), depart_step)
