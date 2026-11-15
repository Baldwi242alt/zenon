"""Loading inputs, building the shared route file (schema 2.8), and checking it.

Inputs:  shared/rover.json (Dhiran), shared/grid_SITE.json (Baldwin)
Output:  shared/route_SITE.json (Harril)

Until Dhiran commits shared/rover.json, the placeholder rover from the
handbook (planner/fake/rover_fake.json, the schema 2.6 example values) is used
and every output says so.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "shared"
FAKE_ROVER = ROOT / "planner" / "fake" / "rover_fake.json"

ROUTE_FIELDS = ("name", "label", "survived", "frozen_at_index", "distance_m", "duration_h", "energy_used_wh",
                "min_battery_pct", "survival_probability", "steps")
STEP_FIELDS = ("t_h", "row", "col", "action", "sun_pct", "power_in_w", "power_out_w", "battery_wh")
LABELS = {"shortest": "Shortest path", "sunchaser_fast": "Sunchaser (fastest safe)",
          "sunchaser_safe": "Sunchaser (max margin)"}


def load_rover():
    """Returns (rover dict, where it came from)."""
    real = SHARED / "rover.json"
    if real.exists():
        return json.loads(real.read_text()), "shared/rover.json"
    return json.loads(FAKE_ROVER.read_text()), ("PLACEHOLDER rover (planner/fake/rover_fake.json, the "
                                                "handbook's example values; shared/rover.json not committed yet)")


def load_grid(site):
    return json.loads((SHARED / f"grid_{site}.json").read_text())


def route_entry(name, result, mc):
    """One entry of the routes list, in schema order."""
    return {
        "name": name, "label": LABELS[name],
        "survived": result["survived"], "frozen_at_index": result["frozen_at_index"],
        "distance_m": result["distance_m"], "duration_h": result["duration_h"],
        "energy_used_wh": result["energy_used_wh"], "min_battery_pct": result["min_battery_pct"],
        "survival_probability": round(mc["survival_probability"], 3),
        "steps": result["steps"],
    }


def check_route_file(data, world):
    """Self-checks from the handbook (5.11) plus the schema. Returns a list of problems."""
    errors = []
    for key in ("site", "start", "target", "depart_step", "monte_carlo_runs", "routes"):
        if key not in data:
            errors.append(f"missing '{key}'")
    if errors:
        return errors
    reserve = world.min_soc * world.cap
    for route in data["routes"]:
        name = route.get("name", "?")
        if tuple(route.keys()) != ROUTE_FIELDS:
            errors.append(f"{name}: fields {list(route.keys())} do not match the schema")
            continue
        steps = route["steps"]
        if not steps or steps[0]["action"] != "start":
            errors.append(f"{name}: must begin with a start step")
            continue
        if (steps[0]["row"], steps[0]["col"]) != (data["start"]["row"], data["start"]["col"]):
            errors.append(f"{name}: does not begin at the start cell")
        if not 0 <= route["survival_probability"] <= 1:
            errors.append(f"{name}: survival_probability out of range")
        prev = steps[0]
        for i, st in enumerate(steps):
            if tuple(st.keys()) != STEP_FIELDS:
                errors.append(f"{name} step {i}: fields do not match the schema")
                break
            if st["battery_wh"] > world.cap + 0.05:
                errors.append(f"{name} step {i}: battery above capacity")
            if not world.drivable(st["row"], st["col"]) and i < len(steps):
                errors.append(f"{name} step {i}: on a cell too steep to drive")
            if i:
                if st["t_h"] <= prev["t_h"] - 1e-9:
                    errors.append(f"{name} step {i}: time does not increase")
                dr, dc = abs(st["row"] - prev["row"]), abs(st["col"] - prev["col"])
                if st["action"] == "move":
                    a, b = world.idx(prev["row"], prev["col"]), world.idx(st["row"], st["col"])
                    if max(dr, dc) != 1 or not any(m[0] == b for m in world.moves[a]):
                        errors.append(f"{name} step {i}: move is not to an allowed neighbouring cell")
                elif st["action"] == "wait":
                    if dr or dc:
                        errors.append(f"{name} step {i}: a wait changed cell")
                else:
                    errors.append(f"{name} step {i}: unknown action {st['action']!r}")
            if name.startswith("sunchaser") and st["battery_wh"] < reserve - 0.05:
                errors.append(f"{name} step {i}: battery {st['battery_wh']} Wh is below the reserve")
            prev = st
        last = steps[-1]
        arrived = (last["row"], last["col"]) == (data["target"]["row"], data["target"]["col"])
        if route["survived"] and not arrived:
            errors.append(f"{name}: survived but did not reach the target")
        if not route["survived"] and route["frozen_at_index"] != len(steps) - 1:
            errors.append(f"{name}: frozen_at_index should be the last step")
        if route["survived"] and route["frozen_at_index"] is not None:
            errors.append(f"{name}: survived routes must have frozen_at_index null")
    names = [r["name"] for r in data["routes"]]
    if "sunchaser_fast" in names and "sunchaser_safe" in names:
        fast = next(r for r in data["routes"] if r["name"] == "sunchaser_fast")
        safe = next(r for r in data["routes"] if r["name"] == "sunchaser_safe")
        if safe["survival_probability"] < fast["survival_probability"] - 1e-9:
            errors.append("the safe route has a lower survival probability than the fast one")
    return errors
