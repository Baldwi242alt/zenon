"""Hand-checkable tests for the shadow grid on flat fake terrain."""

import numpy as np

from sunchaser_data.dem import PolarDEM
from sunchaser_data.grid import ShadowGrid
from test_two_res import write_dem


def flat_grid(tmp_path):
    near = PolarDEM(write_dem(tmp_path, "near", np.zeros((801, 801)), 20), lazy=True)
    far = PolarDEM(write_dem(tmp_path, "far", np.zeros((201, 201)), 1000))
    # -89.99 deg is ~300 m from the pole, inside both small fake maps.
    return ShadowGrid(near, far, -89.99, 0.0, rows=8, cols=8, cell_size_m=40.0)


def test_flat_ground_is_flat(tmp_path):
    g = flat_grid(tmp_path)
    assert np.allclose(g.elevation, 0.0) and np.allclose(g.slope, 0.0)
    # On flat ground the horizon is just below 0 degrees in every direction
    # (2 m mast + curvature), never above.
    assert g.horizon.max() < 0 and g.horizon.min() > -0.2


def test_sun_above_and_below(tmp_path):
    g = flat_grid(tmp_path)
    assert (g.sun_pct([0.0], [1.0]) == 100).all()    # 1 deg up: fully visible everywhere
    assert (g.sun_pct([0.0], [-1.0]) == 0).all()     # 1 deg down: hidden everywhere


def test_cells_closer_to_the_sun_see_it_higher(tmp_path):
    # Sun due north, sitting right at the horizon. The Moon curves away, so
    # cells further north (closer to the Sun) see more of its disk.
    g = flat_grid(tmp_path)
    north_rc = np.array(g.north_c)
    pct = g.sun_pct([0.0], [-0.09])[0].astype(float)
    # Order cells by how far north they are, compare the two extremes.
    far_north = pct[g.off_north == g.off_north.max()].mean()
    far_south = pct[g.off_north == g.off_north.min()].mean()
    assert far_north > far_south
    assert north_rc[0] < 0  # at 0 deg longitude, north points up the grid
