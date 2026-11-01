"""Hand-checkable tests for the core maths (run: python -m pytest data/tests)."""

import math

import numpy as np
import pytest

from sunchaser_data.constants import SUN_ANGULAR_RADIUS_DEG as R
from sunchaser_data.horizon import (
    bilinear_sample,
    curvature_drop_m,
    horizon_profile,
    interp_horizon,
)
from sunchaser_data.metrics import PLACEHOLDER_CRITERIA, longest_run, window_metrics
from sunchaser_data.sunfrac import sun_visible_fraction


# ---------- Sun disk fraction ----------

def test_sun_centre_on_horizon_is_half_visible():
    assert sun_visible_fraction(1.0, 1.0) == pytest.approx(0.5)


def test_sun_fully_above_and_below():
    assert sun_visible_fraction(R, 0.0) == pytest.approx(1.0)
    assert sun_visible_fraction(-R, 0.0) == pytest.approx(0.0)
    assert sun_visible_fraction(5.0, 0.0) == 1.0
    assert sun_visible_fraction(-5.0, 0.0) == 0.0


def test_sun_fraction_is_symmetric_and_increasing():
    # Raising the Sun by d shows as much extra as lowering it by d hides.
    for d in (0.05, 0.1, 0.2):
        assert sun_visible_fraction(d, 0) + sun_visible_fraction(-d, 0) == pytest.approx(1.0)
    d = np.linspace(-0.4, 0.4, 81)
    assert np.all(np.diff(sun_visible_fraction(d, 0.0)) >= 0)


# ---------- Lunar curvature ----------

def test_curvature_drop_matches_handbook_figures():
    # Handbook: about 29 m at 10 km and 720 m at 50 km.
    assert curvature_drop_m(10_000) == pytest.approx(28.78, abs=0.05)
    assert curvature_drop_m(50_000) == pytest.approx(719.5, abs=0.5)


# ---------- DEM sampling and horizon ----------

def test_bilinear_sample_midpoint_and_outside():
    dem = np.array([[0.0, 10.0], [20.0, 30.0]])
    assert bilinear_sample(dem, np.array([0.5]), np.array([0.5]))[0] == pytest.approx(15.0)
    assert np.isnan(bilinear_sample(dem, np.array([5.0]), np.array([0.0]))[0])


def test_flat_plain_horizon_is_slightly_negative():
    # On a perfectly flat map the horizon is below 0 degrees, because the
    # observer stands on a 2 m mast and the surface curves away.
    dem = np.zeros((101, 101))
    prof = horizon_profile(dem, 100.0, 50, 50, np.arange(0, 360, 10))
    assert np.all(prof < 0)
    assert np.all(prof > -2)


def test_wall_horizon_matches_hand_calculation():
    # A 100 m tall wall 1 km north of the observer (10 cells of 100 m).
    dem = np.zeros((41, 41))
    dem[10, :] = 100.0  # row 10 is 10 rows "up" from row 20 = 1,000 m north
    prof = horizon_profile(dem, 100.0, 20, 20, np.array([0.0, 180.0]), mast_m=0.0)
    expected = math.degrees(math.atan2(100.0 - curvature_drop_m(1000.0), 1000.0))
    assert prof[0] == pytest.approx(expected, abs=0.01)  # looking north: ~5.71 degrees
    assert prof[1] < 0.5  # looking south: nothing there


def test_interp_horizon_wraps_around_north():
    az = np.arange(0, 360, 90.0)       # 0, 90, 180, 270
    prof = np.array([4.0, 0.0, 0.0, 2.0])
    # Halfway between 270 (2.0) and 360=0 (4.0) is 315 -> 3.0
    assert interp_horizon(prof, az, 315.0) == pytest.approx(3.0)


# ---------- Mission metrics ----------

def test_longest_run():
    assert longest_run([True, True, False, True, True, True, False]) == 3
    assert longest_run([]) == 0


def test_window_metrics_hand_case():
    # Two days. Day 1: 14 sunlit hours, 6 contact hours -> usable.
    # Day 2: 10 sunlit hours -> not usable (needs 12).
    sun = [1.0] * 14 + [0.0] * 10 + [1.0] * 10 + [0.0] * 14
    earth = [True] * 6 + [False] * 18 + [True] * 6 + [False] * 18
    m = window_metrics(sun, earth, PLACEHOLDER_CRITERIA)
    assert m["usable_days"] == 1.0
    assert m["sun_hours"] == 24.0
    assert m["contact_hours"] == 12.0
    assert m["both_hours"] == 12.0
    assert m["longest_dark_h"] == 14.0
    assert m["survives"] is True  # 14 h <= 18 h
