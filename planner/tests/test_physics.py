from sunchaser.physics import *

rover = {
  "mass_kg": 120,
  "panel": {"area_m2": 0.6, "efficiency": 0.30},
  "battery": {"capacity_wh": 2000, "min_soc": 0.15, "charge_efficiency": 0.95},
  "power_w": {"avionics": 30, "heater_dark": 60, "heater_lit": 0},
  "drive": {"speed_m_per_h": 200, "base_drive_w": 40, "rolling_resistance": 0.15, "drivetrain_efficiency": 0.5}
}

def test_panel():
    # Should be 1361 * 0.6 * 0.30 = 244.98
    assert round(panel_peak_w(rover), 2) == 244.98

def test_heater():
    assert heater_w(rover, 0) == 60
    assert heater_w(rover, 100) == 0

def test_drive_flat():
    # 120 * 1.62 * (200/3600) * 0.15 / 0.5 = 3.24 W mechanical + 40 base = 43.24 W
    assert round(drive_w(rover, 1800, 1800, 40), 2) == 43.24

def test_battery():
    # Parked in dark: 30 avionics + 60 heater = 90W out. 0W in.
    e, frozen, reserve = battery_step(rover, 2000, 0, 90, 1.0)
    assert e == 1910
    assert frozen is False
    