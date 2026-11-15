"""Checks on the real route files in shared/ (skipped for sites whose route isn't built)."""

import json
from pathlib import Path

import pytest

from sunchaser.io import SHARED, check_route_file, load_rover
from sunchaser.sim import simulate
from sunchaser.world import World

SITES = [s["id"] for s in json.loads((SHARED / "sites.json").read_text())]


@pytest.mark.parametrize("site", SITES)
def test_route_file_is_valid_and_replays_exactly(site):
    path = SHARED / f"route_{site}.json"
    if not path.exists():
        pytest.skip("route not built")
    data = json.loads(path.read_text())
    grid = json.loads((SHARED / f"grid_{site}.json").read_text())
    rover, _ = load_rover()
    world = World(grid, rover)

    # Schema + the handbook's self-checks (5.11): allowed moves only, time increases,
    # battery never above capacity, Sunchaser never below the reserve, probabilities in range.
    assert check_route_file(data, world) == []
    assert data["monte_carlo_runs"] == 500

    names = [r["name"] for r in data["routes"]]
    assert names[0] == "shortest" and "sunchaser_fast" in names

    for route in data["routes"]:
        # Rebuild the plan from the published steps and replay it: the simulator must
        # reproduce the published battery trace (the file is not hand-edited).
        steps = route["steps"]
        plan = [("start", steps[0]["row"], steps[0]["col"], 0.0)]
        for prev, st in zip(steps, steps[1:]):
            plan.append((st["action"], st["row"], st["col"], st["t_h"] - prev["t_h"]))
        if route["survived"]:
            replay = simulate(world, plan, data["depart_step"])
            assert replay["survived"]
            assert replay["steps"][-1]["battery_wh"] == pytest.approx(steps[-1]["battery_wh"], abs=2.0)
            assert replay["min_battery_pct"] == pytest.approx(route["min_battery_pct"], abs=0.3)
        if route["name"].startswith("sunchaser"):
            assert route["survived"]
            last = steps[-1]
            assert (last["row"], last["col"]) == (data["target"]["row"], data["target"]["col"])
            # Safe arrival: 24 more hours parked at the target never breach the reserve.
            parked = simulate(world, plan + [("wait", last["row"], last["col"], 24.0)], data["depart_step"])
            assert parked["survived"] and not parked["reserve_breached"]

    fast = next(r for r in data["routes"] if r["name"] == "sunchaser_fast")
    shortest = data["routes"][0]
    assert fast["survival_probability"] >= shortest["survival_probability"]
