"""Software tests for the hardware bridge (no rover needed)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "planner"))
spec = importlib.util.spec_from_file_location("bridge", ROOT / "hardware" / "bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

ROVER = json.loads((ROOT / "planner" / "fake" / "rover_fake.json").read_text())


def step(t, r, c, action="move", sun=100):
    return {"t_h": t, "row": r, "col": c, "action": action, "sun_pct": sun}


def test_straight_line_merges_into_one_forward():
    steps = [step(0, 5, 5, "start"), step(0.2, 4, 5), step(0.4, 3, 5), step(0.6, 2, 5)]
    assert bridge.route_to_commands(steps) == ["F 3.00"]          # heading starts "up the grid"


def test_turns_take_the_short_way_and_diagonals_are_longer():
    steps = [step(0, 5, 5, "start"), step(0.2, 5, 6), step(0.5, 4, 7), step(0.7, 4, 6)]
    # right 90 to face +col, forward 1; left 45 to face up-right, forward 1.41; then face -col: left 135.
    assert bridge.route_to_commands(steps) == ["R 90", "F 1.00", "L 45", "F 1.41", "L 135", "F 1.00"]


def test_waits_become_seconds():
    steps = [step(0, 5, 5, "start"), step(1.0, 5, 5, "wait"), step(1.2, 4, 5)]
    assert bridge.route_to_commands(steps, seconds_per_hour=2.0) == ["W 2.00", "F 1.00"]


def test_light_mapping_clamps_to_0_100():
    assert bridge.light_to_sun_pct(80, 80, 900) == 0
    assert bridge.light_to_sun_pct(900, 80, 900) == 100
    assert bridge.light_to_sun_pct(490, 80, 900) == pytest.approx(50)
    assert bridge.light_to_sun_pct(5, 80, 900) == 0 and bridge.light_to_sun_pct(1023, 80, 900) == 100


def test_battery_loop_parks_to_recharge_in_the_light_but_not_in_the_dark():
    loop = bridge.BatteryLoop(ROVER, seconds_per_hour=1.0)
    actions = [loop.update(0, 1.0, driving=True) for _ in range(13)]       # 13 simulated hours driving in the dark
    # 133 W in the dark: the 300 Wh reserve is crossed after 12.8 h. No STOP: parking in the dark can't help.
    assert loop.energy < loop.reserve and "STOP" not in actions and not loop.paused
    assert loop.update(100, 0.1, driving=True) == "STOP" and loop.paused   # reaches the light: park and charge
    actions = [loop.update(100, 1.0, driving=True) for _ in range(4)]      # parked in the Sun: +204 Wh per hour
    assert "GO" in actions and not loop.paused


def test_simulated_run_of_a_real_route_completes():
    path = ROOT / "shared" / "route_slater_plain.json"
    if not path.exists():
        pytest.skip("route not built")
    data = json.loads(path.read_text())
    route = next(r for r in data["routes"] if r["name"] == "sunchaser_fast")
    sph = bridge.seconds_per_sim_hour(route["steps"], bridge.FakeRover.MS_PER_CELL)
    link = bridge.FakeRover(route["steps"], seconds_per_hour=sph)
    loop = bridge.run(route, ROVER, link, sph, 80, 900, real_time=False, log=lambda m: None)
    assert not loop.frozen


def test_time_scale_matches_the_plans_pace():
    # The plan takes 0.4 simulated hours per cell; the rover takes 1.2 real seconds per cell:
    # 3 real seconds per simulated hour.
    steps = [step(0, 5, 5, "start"), step(0.4, 4, 5), step(0.8, 3, 5)]
    assert bridge.seconds_per_sim_hour(steps, 1200) == pytest.approx(3.0)
