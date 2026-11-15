"""Rover energy physics (owner: Harril).

Every equation the planner and simulator use lives here, one small function
each, so each can be checked by hand (see tests/test_physics.py).

Units: power in watts (W), energy in watt-hours (Wh), time in hours,
distance in metres, sun_pct as 0-100.
"""

import math

SOLAR_CONSTANT_W_M2 = 1361.0   # sunlight at the Moon's distance from the Sun
LUNAR_GRAVITY_M_S2 = 1.62
DARK_THRESHOLD_PCT = 5         # below this much Sun, survival heaters switch on


def panel_peak_w(rover):
    """Most power the solar panel can make, in full sunlight.

    The panel is vertical and tracks the Sun, and at the south pole the Sun is
    within about 1.5 degrees of the horizon, so the panel faces it almost
    square-on: the angle loss (cosine of the Sun's elevation) is under 0.04%
    and is ignored.
    """
    return SOLAR_CONSTANT_W_M2 * rover["panel"]["area_m2"] * rover["panel"]["efficiency"]


def power_in_w(rover, sun_pct):
    """Solar power right now: peak power times the visible share of the Sun's disk."""
    return panel_peak_w(rover) * (sun_pct / 100.0)


def heater_w(rover, sun_pct):
    """Heater power: survival heaters run when the rover is in the dark (Sun under 5%)."""
    if sun_pct < DARK_THRESHOLD_PCT:
        return rover["power_w"]["heater_dark"]
    return rover["power_w"]["heater_lit"]


def drive_w(rover, elev_here, elev_next, horizontal_m):
    """Power needed to drive from one cell to the next, including the slope.

    mechanical = mass * g * speed * (rolling_resistance * cos(slope) + sin(slope))
    drive      = base_drive + max(0, mechanical) / drivetrain_efficiency

    Going downhill gives nothing back (no regenerative braking). Returns 0 when
    the rover isn't moving.
    """
    if horizontal_m == 0:
        return 0.0
    v = rover["drive"]["speed_m_per_h"] / 3600.0          # metres per second
    theta = math.atan((elev_next - elev_here) / horizontal_m)
    rr = rover["drive"]["rolling_resistance"]
    mech_w = rover["mass_kg"] * LUNAR_GRAVITY_M_S2 * v * (rr * math.cos(theta) + math.sin(theta))
    mech_w = max(0.0, mech_w)
    return rover["drive"]["base_drive_w"] + mech_w / rover["drive"]["drivetrain_efficiency"]


def power_out_w(rover, sun_pct, drive_power_w=0.0):
    """Total power the rover draws: avionics + heaters (if dark) + driving (if moving)."""
    return rover["power_w"]["avionics"] + heater_w(rover, sun_pct) + drive_power_w


def battery_step(rover, energy_wh, power_in, power_out, dt_h):
    """Move the battery forward by dt_h hours at constant power.

    Charging loses a little to charge_efficiency; discharging is counted in
    full. The battery can't hold more than its capacity.
    Returns (new_energy_wh, frozen, reserve_breached):
      frozen           the battery hit zero: the rover is dead
      reserve_breached the battery is below the safety reserve (min_soc)
    """
    capacity = rover["battery"]["capacity_wh"]
    net_power = power_in - power_out
    if net_power > 0:
        energy_wh += net_power * rover["battery"]["charge_efficiency"] * dt_h
    else:
        energy_wh += net_power * dt_h
    energy_wh = min(energy_wh, capacity)
    frozen = energy_wh <= 0
    reserve_breached = energy_wh < rover["battery"]["min_soc"] * capacity
    return energy_wh, frozen, reserve_breached


def dark_endurance_h(rover, to_reserve=True):
    """Hours a parked rover lasts in darkness from a full battery (to the reserve, or to empty)."""
    cap = rover["battery"]["capacity_wh"]
    usable = cap * (1 - rover["battery"]["min_soc"]) if to_reserve else cap
    return usable / power_out_w(rover, 0)
