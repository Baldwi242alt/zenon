"""The Sunchaser planner: space-time A* with a battery, waiting, and dominance pruning.

The naive planner (astar2d) searches over cells. This one searches over
STATES: (cell, time, battery energy). From each state the rover can
  - MOVE to one of up to 8 neighbouring cells (takes distance / speed hours), or
  - WAIT in place (1 hour, or half an hour), charging if the cell is sunlit.
The battery is moved forward with exactly the same function the simulator uses
(World.advance), and any action that would take it below the safety reserve is
thrown away. So the planner learns by itself to park in sunlight while a shadow
passes, or to go around it.

Goal: reach the target as early as possible. A* orders states by
    f = time so far + (straight-line "octile" distance left) / speed
The second term is the fastest the rover could possibly still arrive, so it
never overestimates: the first time the target is popped, that arrival time is
the fastest found. Among routes that arrive at that same time, the one with the
most battery left is returned (same speed, more margin).

Keeping the search small: dominance pruning
-------------------------------------------
Adding time and energy makes the number of states explode: there are thousands
of ways to reach a cell at slightly different times with slightly different
charge. Most are pointless. If label A reached a cell earlier than label B,
and A could simply wait there until B's arrival time and still have at least
as much energy as B, then anything B can do from here, A can do as well:
B is "dominated" and is dropped. Each cell keeps only its non-dominated labels.
This is the standard technique for resource-constrained shortest paths.

One care point: a WAIT step's result is by definition "its parent, having
waited", so it would always be dominated by its own parent. Labels therefore
remember which arrival they descend from by waiting (their origin), and are
never compared against their own wait-chain.

Waiting is only tried where it can matter: when the rover can charge (sunlit
and battery not full), or when sunlight in or next to the cell changes within
the next two days (a shadow edge is arriving or leaving).

Arriving safely: reaching the target only counts if the rover could then stay
parked there for 24 hours without breaching its reserve. Otherwise the planner
would happily "arrive" in the dark with an almost empty battery.

Honest limits: time is continuous but waits come in fixed steps, so the
"fastest" route is the fastest among routes built from those steps; the grid
is 8-connected; the rover starts with a full battery.
"""

import heapq
import time

EPS_T = 1e-9
EPS_E = 1e-6


def change_soon_table(world, horizon_h=48, min_change_pct=10):
    """For every hour and cell: does sunlight in the cell or a neighbour change within horizon_h?

    Returned as a list (per hour) of bytearrays (per cell). Built with numpy
    when available because it is a pure array operation.
    """
    import numpy as np

    sun = np.asarray(world.grid["sun_pct"], dtype=np.int16)            # (steps, rows, cols)
    n = sun.shape[0]
    hi, lo = sun.copy(), sun.copy()
    for k in range(1, min(horizon_h, n - 1) + 1):                       # max/min over the next hours
        hi[:n - k] = np.maximum(hi[:n - k], sun[k:])
        lo[:n - k] = np.minimum(lo[:n - k], sun[k:])
    changes = (hi - lo) >= min_change_pct
    near = changes.copy()                                               # spread to the 8 neighbours
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            shifted = np.zeros_like(changes)
            r0, r1 = max(dr, 0), changes.shape[1] + min(dr, 0)
            c0, c1 = max(dc, 0), changes.shape[2] + min(dc, 0)
            shifted[:, r0:r1, c0:c1] = changes[:, r0 - dr:r1 - dr, c0 - dc:c1 - dc]
            near |= shifted
    flat = near.reshape(n, -1).astype(np.uint8)
    return [bytearray(row.tobytes()) for row in flat]


def plan_route(world, start, target, depart_step, reserve_frac=None, start_energy=None,
               start_t=0.0, wait_steps=(1.0, 0.5), panel_scale=1.0, max_labels=1_500_000,
               change_soon=None, dominance=True, settle_h=24.0, max_seconds=300.0):
    """Fastest route that never takes the battery below the reserve.

    world        World (grid + rover)
    start/target (row, col)
    depart_step  hour index in the grid when the rover leaves
    reserve_frac battery share to keep in hand (default: rover's min_soc)
    start_energy battery at the start in Wh (default: full); start_t hours already
                 elapsed since depart_step; panel_scale: all three are used when
                 replanning mid-route (for example after dust reduces panel output)
    settle_h     arriving only counts if the rover could then stay parked at the
                 target for this many hours without breaching the reserve (so it
                 never "arrives" into a long shadow with an almost empty battery)
    dominance    False switches dominance pruning off (only exact duplicates are
                 dropped, and waiting is always allowed). Far slower; exists so the
                 tests can prove that pruning does not change the answer.
    Returns (plan, stats). plan is a list of ("start"|"move"|"wait", row, col,
    duration_h), or None if no safe route exists inside the grid's time window.
    """
    cap = world.cap
    reserve = cap * (world.min_soc if reserve_frac is None else reserve_frac)
    s_idx, g_idx = world.idx(*start), world.idx(*target)
    stats = {"labels": 0, "expanded": 0, "pruned": 0, "reason": ""}
    if not world.moves[s_idx] or not world.moves[g_idx]:
        stats["reason"] = "start or target is not drivable"
        return None, stats
    t_end = world.n_steps - depart_step                 # hours available
    speed = world.speed
    moves = world.moves
    advance, move_energy = world.advance, world.move_energy
    if change_soon is None:
        change_soon = change_soon_table(world)
    n_steps = world.n_steps
    peak01 = world.peak * panel_scale * 0.01
    base_out = world.avionics
    heater_dark, heater_lit = world.heater_dark, world.heater_lit
    sun = world.sun
    octile = world.octile_m
    # Fastest the battery can possibly charge while parked (W, after charging losses).
    max_gain = max(0.0, world.peak * panel_scale - base_out - heater_lit) * world.eff

    e0 = cap if start_energy is None else start_energy
    # nodes: parallel lists (cell, t, energy, parent, action, duration, origin)
    n_cell, n_t, n_e, n_parent, n_act, n_dur, n_origin = [s_idx], [start_t], [e0], [-1], ["start"], [0.0], [0]
    alive = bytearray([1])
    labels = {s_idx: [0]}                               # cell -> node ids of non-dominated labels
    heap = [(start_t + octile(s_idx, g_idx) / speed, -start_t, 0)]

    def waited(cell, t_from, e_from, t_to):
        """Energy if a rover at `cell` waits from t_from to t_to; None if it would breach the reserve."""
        if t_to - t_from < EPS_T:
            return e_from
        e, low, froze = advance(cell, depart_step + t_from, t_to - t_from, e_from, 0.0, cap, panel_scale, 1.0)
        if froze is not None or low < reserve - EPS_E:
            return None
        return e

    seen = set()

    def add(cell, t, e, parent, action, dur, origin):
        """Add a label unless an existing one dominates it. Returns the node id or None."""
        ids = labels.get(cell)
        if not dominance:
            key = (cell, round(t, 6), round(e, 3))
            if key in seen:
                return None
            seen.add(key)
            ids = None
        if ids:
            for i in ids:
                ti = n_t[i]
                dt = t - ti
                if n_origin[i] == origin:
                    if -EPS_T < dt < EPS_T:
                        stats["pruned"] += 1
                        return None                      # the same wait-chain reached the same moment twice
                    continue                             # otherwise never compare within a wait-chain
                if dt < -EPS_T:
                    continue                             # the existing label is later: it can't dominate
                ei = n_e[i]
                if dt < EPS_T:
                    if ei >= e - EPS_E:
                        stats["pruned"] += 1
                        return None                      # same time, at least as much energy
                elif ei + max_gain * dt >= e - EPS_E:    # could it have enough after waiting? check exactly
                    ew = waited(cell, ti, ei, t)
                    if ew is not None and ew >= e - EPS_E:
                        stats["pruned"] += 1
                        return None
            # Drop existing labels that the new one dominates.
            keep = []
            for i in ids:
                if n_origin[i] != origin and t <= n_t[i] + EPS_T:
                    ew = waited(cell, t, e, n_t[i]) if e + max_gain * (n_t[i] - t) >= n_e[i] - EPS_E else None
                    if ew is not None and ew >= n_e[i] - EPS_E:
                        alive[i] = 0
                        continue
                keep.append(i)
            labels[cell] = keep
        else:
            labels[cell] = keep = []
        nid = len(n_cell)
        n_cell.append(cell); n_t.append(t); n_e.append(e); n_parent.append(parent)
        n_act.append(action); n_dur.append(dur)
        n_origin.append(nid if origin < 0 else origin)
        alive.append(1)
        keep.append(nid)
        stats["labels"] += 1
        return nid

    n_origin[0] = 0
    goal, goal_t = -1, 0.0
    deadline = time.time() + max_seconds          # hopeless searches spend their time rejecting labels

    def finish(nid):
        plan = []
        while nid >= 0:
            r, c = world.rc(n_cell[nid])
            plan.append((n_act[nid], r, c, n_dur[nid]))
            nid = n_parent[nid]
        plan.reverse()
        stats["reason"] = "ok"
        return plan, stats

    while heap:
        f, neg_t, nid = heapq.heappop(heap)
        if goal >= 0 and f > goal_t + 1e-6:
            break                                        # nothing left can arrive as early
        if not alive[nid]:
            continue
        cell, t, e = n_cell[nid], n_t[nid], n_e[nid]
        if cell == g_idx and waited(cell, t, e, min(t + settle_h, t_end)) is not None:
            # A real arrival: the rover can also sit here safely for settle_h hours.
            # First arrival fixes the fastest time. Keep looking only among routes that
            # arrive at that same time, and keep the one with the most battery left:
            # equal speed, more margin.
            if goal < 0 or e > n_e[goal] + EPS_E:
                goal, goal_t = nid, t
            continue
        stats["expanded"] += 1
        if stats["labels"] > max_labels or (stats["expanded"] % 2000 == 0 and time.time() > deadline):
            if goal >= 0:
                return finish(goal)
            stats["reason"] = "search limit reached"
            return None, stats
        t_abs = depart_step + t

        # --- MOVE to each allowed neighbour ---
        for nb, dur, drive, _dist in moves[cell]:
            t2 = t + dur
            if t2 > t_end:
                continue
            e2, low, froze = move_energy(cell, nb, dur, drive, t_abs, e, cap, panel_scale, 1.0)
            if froze is not None or low < reserve - EPS_E:
                continue
            new = add(nb, t2, e2, nid, "move", dur, -1)
            if new is not None:
                heapq.heappush(heap, (t2 + octile(nb, g_idx) / speed, -t2, new))

        # --- WAIT here, if waiting can help ---
        step = int(t_abs)
        if step >= n_steps:
            continue
        pct = sun[step][cell]
        charging = e < cap - EPS_E and peak01 * pct > base_out + (heater_dark if pct < 5 else heater_lit)
        if charging or not dominance or change_soon[step][cell]:
            for w in wait_steps:
                t2 = t + w
                if t2 > t_end:
                    continue
                e2, low, froze = advance(cell, t_abs, w, e, 0.0, cap, panel_scale, 1.0)
                if froze is not None or low < reserve - EPS_E:
                    continue
                new = add(cell, t2, e2, nid, "wait", w, n_origin[nid])
                if new is not None:
                    heapq.heappush(heap, (t2 + octile(cell, g_idx) / speed, -t2, new))

    if goal >= 0:
        return finish(goal)
    stats["reason"] = "no safe route inside the time window"
    return None, stats


def astar_spacetime(grid, rover, start, target, depart_step):
    """Harril's original entry point. Returns the plan (see plan_route) or None."""
    from .world import World
    plan, _ = plan_route(World(grid, rover), tuple(start), tuple(target), depart_step)
    return plan
