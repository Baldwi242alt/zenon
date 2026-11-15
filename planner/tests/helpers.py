"""Tiny hand-made worlds for the planner tests."""

import copy
import json
from pathlib import Path

ROVER = json.loads((Path(__file__).resolve().parents[1] / "fake" / "rover_fake.json").read_text())


def rover(**battery):
    """The handbook's example rover, optionally with a different battery (e.g. capacity_wh=200)."""
    r = copy.deepcopy(ROVER)
    r["battery"].update(battery)
    return r


def make_grid(rows, cols, n_steps, sun=lambda s, r, c: 100, elev=lambda r, c: 0.0, slope=lambda r, c: 0.0,
              cell=40.0):
    return {
        "site": "test", "window_start": "2027-01-01T00:00Z", "step_h": 1, "n_steps": n_steps,
        "rows": rows, "cols": cols, "cell_size_m": cell, "center": {"lat": -89.0, "lon": 0.0},
        "orientation_note": "test grid",
        "elevation_m": [[elev(r, c) for c in range(cols)] for r in range(rows)],
        "slope_deg": [[slope(r, c) for c in range(cols)] for r in range(rows)],
        "sun_pct": [[[sun(s, r, c) for c in range(cols)] for r in range(rows)] for s in range(n_steps)],
    }
