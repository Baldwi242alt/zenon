"""Hand-checkable test of the two-resolution horizon (near DEM + far DEM).

We write two tiny fake south-polar DEM files in the LOLA format:
  - a sharp "near" DEM (10 m cells) with a 50 m high plateau starting 500 m
    north of the observer;
  - a coarse "far" DEM (100 m cells) with a 2,000 m plateau starting 20 km south.
(Plateaus, not one-pixel walls: interpolation between pixels would shave a
one-pixel wall, and real terrain is never that sharp.)
The combined horizon must see the near wall looking north and the far wall
looking south, each at the angle we can work out by hand.
"""

import math

import numpy as np
import pytest

from sunchaser_data.dem import PolarDEM
from sunchaser_data.horizon import curvature_drop_m
from sunchaser_data.illumination import PROFILE_AZ, horizon_for_point

LABEL = """    LINES                 = {n}
    LINE_SAMPLES          = {n}
    SCALING_FACTOR        = 0.5
 A_AXIS_RADIUS                = 1737.4 <km>
 CENTER_LATITUDE              = -90 <deg>
 MAP_SCALE                    = {scale} <m/pix>
 LINE_PROJECTION_OFFSET       = {off} <pix>
 SAMPLE_PROJECTION_OFFSET     = {off} <pix>
"""


def write_dem(tmp_path, name, heights, scale):
    n = heights.shape[0]
    (tmp_path / f"{name}.IMG").write_bytes((heights * 2).astype("<i2").tobytes())
    (tmp_path / f"{name}.LBL").write_text(LABEL.format(n=n, scale=scale, off=(n - 1) / 2))
    return tmp_path / f"{name}.IMG"


def test_near_and_far_walls_both_seen(tmp_path):
    # Observer at the pole itself (centre of both maps). At the pole every
    # direction is "north", so use a point just off it on 0 deg longitude,
    # where north points up the map.
    lat, lon = -89.99, 0.0  # about 303 m from the pole, up the map

    near = np.zeros((401, 401))           # 10 m cells, 4 km square
    far = np.zeros((601, 601))            # 100 m cells, 60 km square
    near_path = write_dem(tmp_path, "near", near, 10)
    far_path = write_dem(tmp_path, "far", far, 100)
    near_dem = PolarDEM(near_path, lazy=True)
    far_dem = PolarDEM(far_path)

    # Place the walls relative to the observer's position on each map.
    nr, nc = near_dem.latlon_to_rc(lat, lon)
    fr, fc = far_dem.latlon_to_rc(lat, lon)
    near[: int(round(nr)) - 50 + 1, :] = 50.0   # from 50 rows (500 m) north, outwards
    far[int(round(fr)) + 200:, :] = 2000.0      # from 200 rows (20 km) south, outwards
    write_dem(tmp_path, "near", near, 10)
    write_dem(tmp_path, "far", far, 100)
    near_dem = PolarDEM(near_path, lazy=True)
    far_dem = PolarDEM(far_path)

    prof, coverage, ground = horizon_for_point(far_dem, lat, lon, near_dem=near_dem,
                                               near_m=1_500, max_m=25_000, mast_m=0.0)
    north = prof[PROFILE_AZ == 0.0][0]
    south = prof[PROFILE_AZ == 180.0][0]

    d_n = (round(nr) - 50 - nr) * -10.0   # exact distance to the near wall
    d_s = (round(fr) + 200 - fr) * 100.0  # exact distance to the far wall
    assert ground == pytest.approx(0.0)
    # The ray samples every 10 m, so it meets the plateau edge within one step.
    assert north == pytest.approx(math.degrees(math.atan2(50 - curvature_drop_m(d_n), d_n)), abs=0.12)
    # Beyond 20 km the ray samples every 1% of the distance (about 200 m here),
    # so it can meet the edge up to ~1% late: about 0.06 deg at 5.4 deg.
    assert south == pytest.approx(math.degrees(math.atan2(2000 - curvature_drop_m(d_s), d_s)), abs=0.1)
    assert coverage == 1.0
