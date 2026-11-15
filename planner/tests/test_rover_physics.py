"""Hand-checkable physics (the table in the handbook, section 5.4)."""

import math

import pytest

from sunchaser import physics
from sunchaser.physics import battery_step, drive_w, heater_w, panel_peak_w, power_in_w, power_out_w
from helpers import rover as make_rover

rover = make_rover()


def test_panel():
    # 1361 * 0.6 * 0.30 = 244.98 W
    assert round(panel_peak_w(rover), 2) == 244.98
    assert power_in_w(rover, 50) == pytest.approx(122.49)


def test_heater():
    assert heater_w(rover, 0) == 60
    assert heater_w(rover, 4) == 60        # under 5% Sun still counts as dark
    assert heater_w(rover, 100) == 0


def test_drive_flat():
    # 120 * 1.62 * (200/3600) * 0.15 / 0.5 = 3.24 W mechanical + 40 base = 43.24 W
    assert round(drive_w(rover, 1800, 1800, 40), 2) == 43.24


def test_drive_uphill_15_degrees():
    # 120 * 1.62 * 0.0556 * (0.15 cos 15 + sin 15) / 0.5 = 8.72 W mechanical
    rise = 40 * math.tan(math.radians(15))
    assert drive_w(rover, 0, rise, 40) - 40 == pytest.approx(8.72, abs=0.02)
    # Downhill gives nothing back: just the base drive power.
    assert drive_w(rover, rise, 0, 40) == pytest.approx(40.0)
    assert drive_w(rover, 0, 0, 0) == 0.0


def test_parked_in_the_dark():
    # 30 W avionics + 60 W heater = 90 W out, nothing in.
    assert power_out_w(rover, 0) == 90
    e, frozen, breached = battery_step(rover, 2000, 0, 90, 1.0)
    assert (e, frozen, breached) == (1910, False, False)
    # 2,000 Wh lasts 22.2 h to empty and 18.9 h to the 15% reserve.
    assert physics.dark_endurance_h(rover, to_reserve=False) == pytest.approx(22.2, abs=0.05)
    assert physics.dark_endurance_h(rover) == pytest.approx(18.9, abs=0.05)


def test_parked_in_full_sun_charges_and_caps():
    # net = 244.98 - 30 = 214.98 W, times 0.95 charging efficiency = 204.2 Wh per hour
    e, _, _ = battery_step(rover, 1000, power_in_w(rover, 100), power_out_w(rover, 100), 1.0)
    assert e == pytest.approx(1204.2, abs=0.1)
    e, _, _ = battery_step(rover, 1950, power_in_w(rover, 100), power_out_w(rover, 100), 1.0)
    assert e == 2000                                   # capped at capacity


def test_battery_freezes_and_breaches_reserve():
    e, frozen, breached = battery_step(rover, 50, 0, 90, 1.0)
    assert frozen and breached
    e, frozen, breached = battery_step(rover, 350, 0, 90, 1.0)   # 260 Wh left: under the 300 Wh reserve
    assert not frozen and breached
