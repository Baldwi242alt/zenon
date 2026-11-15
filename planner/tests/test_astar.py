"""Shortest-route planner: hand-checkable cases."""

import math

import pytest

from sunchaser.astar2d import astar_shortest_path, shortest_path
from sunchaser.sim import path_to_plan, simulate
from sunchaser.world import World
from helpers import make_grid, rover


def test_open_grid_gives_straight_diagonal():
    path = astar_shortest_path(make_grid(5, 5, 4), (0, 0), (4, 4), rover())
    assert path == [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)]


def test_wall_with_one_gap_forces_path_through_gap():
    # Column 3 is a steep wall except at row 5.
    grid = make_grid(7, 7, 4, slope=lambda r, c: 30.0 if (c == 3 and r != 5) else 0.0)
    path = astar_shortest_path(grid, (1, 0), (1, 6), rover())
    assert (5, 3) in path
    assert all(grid["slope_deg"][r][c] <= 15 for r, c in path)


def test_step_too_steep_along_the_move_is_blocked():
    # Cells are flat by themselves, but there is a 20 m cliff between columns 1 and 2:
    # atan(20 / 40) = 26.6 deg along the move, above the 15 deg limit.
    grid = make_grid(1, 4, 4, elev=lambda r, c: 0.0 if c < 2 else 20.0)
    assert astar_shortest_path(grid, (0, 0), (0, 3), rover()) is None


def test_no_route_when_target_is_walled_off():
    grid = make_grid(5, 5, 4, slope=lambda r, c: 30.0 if c == 2 else 0.0)
    assert astar_shortest_path(grid, (0, 0), (0, 4), rover()) is None


def test_route_length_is_octile_distance_on_open_ground():
    w = World(make_grid(10, 20, 30), rover())
    path = shortest_path(w, (0, 0), (9, 19))
    r = simulate(w, path_to_plan(w, path), 0)
    assert r["distance_m"] == pytest.approx(40 * (19 + (math.sqrt(2) - 1) * 9), abs=0.2)
    assert r["duration_h"] == pytest.approx(r["distance_m"] / 200, abs=0.01)
