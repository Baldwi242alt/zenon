"""Space-time (Sunchaser) planner: hand-made worlds where the right answer is known."""

import random

import pytest

from sunchaser.astar2d import shortest_path
from sunchaser.astar_st import plan_route
from sunchaser.io import check_route_file, route_entry
from sunchaser.montecarlo import survival_probability
from sunchaser.pareto import pareto_routes
from sunchaser.replan import replan_after_fault
from sunchaser.sim import path_to_plan, simulate
from sunchaser.world import World
from helpers import make_grid, rover


def corridor(dark_until=10, n_steps=40):
    """A 3 x 30 strip. Columns 10-19 are in shadow until hour `dark_until`, then lit."""
    return make_grid(3, 30, n_steps, sun=lambda s, r, c: 0 if (10 <= c < 20 and s < dark_until) else 100)


SMALL = dict(capacity_wh=200)        # small battery: 10 dark cells cost more than it holds


def test_fully_lit_grid_gives_the_shortest_route_with_no_waiting():
    w = World(make_grid(12, 12, 40), rover())
    plan, _ = plan_route(w, (0, 0), (11, 11), 0)
    assert [a[0] for a in plan].count("wait") == 0
    assert [(r, c) for _, r, c, _ in plan] == shortest_path(w, (0, 0), (11, 11))


def test_shortest_route_freezes_in_the_shadow_and_sunchaser_waits_it_out():
    w = World(corridor(), rover(**SMALL))
    naive = simulate(w, path_to_plan(w, shortest_path(w, (1, 0), (1, 29))), 0)
    # Hand check: 2 h to reach the shadow (lit, battery full), then 43.24 + 90 = 133.24 W with no Sun:
    # 200 Wh lasts 1.5 h = 7.5 cells, so it dies inside the 10-cell shadow.
    assert not naive["survived"]
    assert naive["steps"][-1]["battery_wh"] == 0
    assert 10 <= naive["steps"][-1]["col"] < 20
    assert naive["duration_h"] == pytest.approx(2.0 + 200 / 133.24, abs=0.15)

    plan, _ = plan_route(w, (1, 0), (1, 29), 0)
    smart = simulate(w, plan, 0)
    assert smart["survived"] and not smart["reserve_breached"]
    assert any(a[0] == "wait" for a in plan)
    # It can't cross before the shadow lifts at hour 10, and needs 2 h for the last 10 cells,
    # so it arrives soon after hour 12, and long before a rover that waited at the start would.
    assert 12.0 <= smart["duration_h"] <= 14.5
    # While waiting it sits on a sunlit cell, never in the shadow.
    for step in smart["steps"]:
        if step["action"] == "wait":
            assert step["sun_pct"] == 100


def test_sunchaser_detours_around_a_permanent_shadow():
    # A dark block in the middle of the map that never lifts; lit corridor along row 0.
    grid = make_grid(9, 30, 60, sun=lambda s, r, c: 0 if (r >= 2 and 8 <= c < 22) else 100)
    w = World(grid, rover(**SMALL))
    naive = simulate(w, path_to_plan(w, shortest_path(w, (5, 0), (5, 29))), 0)
    assert not naive["survived"]
    plan, _ = plan_route(w, (5, 0), (5, 29), 0)
    smart = simulate(w, plan, 0)
    assert smart["survived"] and smart["distance_m"] > naive["distance_m"]


def test_no_route_is_reported_when_none_is_safe():
    # The target sits deep inside a shadow that never lifts.
    grid = make_grid(3, 40, 30, sun=lambda s, r, c: 0 if c >= 10 else 100)
    plan, stats = plan_route(World(grid, rover(**SMALL)), (1, 0), (1, 39), 0)
    assert plan is None and "no safe route" in stats["reason"]


def test_routes_never_enter_steep_cells_or_drop_below_the_reserve():
    rng = random.Random(7)
    steep = {(rng.randrange(12), rng.randrange(12)) for _ in range(25)} - {(0, 0), (11, 11)}
    grid = make_grid(12, 12, 80, slope=lambda r, c: 30.0 if (r, c) in steep else 2.0,
                     sun=lambda s, r, c: 100 if (s // 6 + c // 4) % 2 == 0 else 0)
    w = World(grid, rover(capacity_wh=150))
    # settle_h=0: this test is about the drive itself (a 150 Wh battery can't park through 6 h of dark).
    plan, _ = plan_route(w, (0, 0), (11, 11), 0, settle_h=0.0)
    assert plan is not None
    result = simulate(w, plan, 0)
    assert result["survived"] and not result["reserve_breached"]
    assert all((r, c) not in steep for _, r, c, _ in plan)
    assert all(s["battery_wh"] >= 0.15 * 150 - 0.05 for s in result["steps"])


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_dominance_pruning_does_not_change_the_answer(seed):
    """On small random worlds, the pruned search arrives at the same time as a brute-force search."""
    rng = random.Random(seed)
    phase = [[rng.randrange(6) for _ in range(6)] for _ in range(4)]
    grid = make_grid(4, 6, 16, sun=lambda s, r, c: 100 if (s + phase[r][c]) % 6 < 3 else 0)
    w = World(grid, rover(capacity_wh=60))
    fast, a = plan_route(w, (0, 0), (3, 5), 0, wait_steps=(1.0,), settle_h=0.0)
    brute, b = plan_route(w, (0, 0), (3, 5), 0, wait_steps=(1.0,), dominance=False, settle_h=0.0)
    assert (fast is None) == (brute is None)
    if fast is not None:
        t_fast = sum(step[3] for step in fast)
        t_brute = sum(step[3] for step in brute)
        assert t_fast == pytest.approx(t_brute, abs=1e-6)
        assert a["labels"] <= b["labels"]


def test_monte_carlo_is_reproducible_and_ranks_routes_sensibly():
    w = World(corridor(), rover(**SMALL))
    naive_plan = path_to_plan(w, shortest_path(w, (1, 0), (1, 29)))
    smart_plan, _ = plan_route(w, (1, 0), (1, 29), 0)
    a = survival_probability(w, smart_plan, 0, n=200)
    b = survival_probability(w, smart_plan, 0, n=200)
    assert a == b                                              # fixed seed
    naive = survival_probability(w, naive_plan, 0, n=200)
    assert 0 <= naive["survival_probability"] < a["survival_probability"] <= 1
    assert naive["survival_probability"] < 0.05               # it needs 266 Wh from a 200 Wh battery


def test_pareto_safer_routes_keep_more_battery():
    w = World(corridor(), rover(**SMALL))
    levels = pareto_routes(w, (1, 0), (1, 29), 0, reserves=[0.15, 0.30, 0.45], runs=100)
    assert [p["reserve_pct"] for p in levels] == [15.0, 30.0, 45.0]
    mins = [p["result"]["min_battery_pct"] for p in levels]
    assert mins[0] >= 15 and mins[1] >= 30 and mins[2] >= 45
    assert levels[-1]["result"]["duration_h"] >= levels[0]["result"]["duration_h"] - 1e-9


def test_replanning_after_a_panel_fault_keeps_the_rover_safe():
    w = World(corridor(dark_until=10, n_steps=80), rover(**SMALL))
    plan, _ = plan_route(w, (1, 0), (1, 29), 0)
    out = replan_after_fault(w, plan, 0, (1, 29), at_fraction=0.3, panel_scale=0.7)
    assert out["replanned"] is not None
    assert out["replanned"]["survived"] and out["replanned"]["reserve_kept"]
    assert out["replanned"]["arrival_t_h"] >= out["fault_at"]["t_h"]


def test_route_file_passes_its_own_checks():
    w = World(corridor(), rover(**SMALL))
    naive_plan = path_to_plan(w, shortest_path(w, (1, 0), (1, 29)))
    smart_plan, _ = plan_route(w, (1, 0), (1, 29), 0)
    data = {"site": "test", "start": {"row": 1, "col": 0}, "target": {"row": 1, "col": 29},
            "depart_step": 0, "monte_carlo_runs": 100,
            "routes": [route_entry("shortest", simulate(w, naive_plan, 0), survival_probability(w, naive_plan, 0, n=100)),
                       route_entry("sunchaser_fast", simulate(w, smart_plan, 0), survival_probability(w, smart_plan, 0, n=100))]}
    assert check_route_file(data, w) == []
    # A tampered route is caught.
    data["routes"][1]["steps"][3]["battery_wh"] = 1.0
    assert any("below the reserve" in e for e in check_route_file(data, w))


def test_arrival_only_counts_if_the_rover_can_stay_alive_at_the_target():
    # The last five columns (the target's neighbourhood) are in shadow until hour 30.
    # With a 200 Wh battery the rover lasts under 2 h parked in the dark, so it must not
    # arrive much before the Sun does, even though it could drive there in 6 hours.
    grid = make_grid(3, 30, 80, sun=lambda s, r, c: 0 if (c >= 25 and s < 30) else 100)
    w = World(grid, rover(**SMALL))
    plan, _ = plan_route(w, (1, 0), (1, 29), 0)
    arrive = sum(step[3] for step in plan)
    assert arrive >= 28.0
    # Replay the route plus 24 h parked at the target: the reserve is never breached.
    parked = simulate(w, plan + [("wait", 1, 29, 24.0)], 0)
    assert parked["survived"] and not parked["reserve_breached"]
    # Without the rule the planner would arrive early, into the dark.
    early, _ = plan_route(w, (1, 0), (1, 29), 0, settle_h=0.0)
    assert sum(step[3] for step in early) < 10.0
