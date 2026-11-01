"""Stage 2 sanity check: a full year of real Sun and Earth positions at one point.

Run:  python data/check_horizons.py [lat] [east_lon] [elevation_m]

Checks the physics we expect at the lunar south pole (CLAUDE.md 1.2):
  - the Sun stays within about 1.5 deg of the horizon, plus up to the
    site's distance from the pole in degrees (a site 0.55 deg from the pole
    sees the Sun up to about 0.55 deg higher on one side of the sky);
  - the Sun's azimuth goes round once per lunar day (about 29.5 days);
  - Earth's elevation swings by roughly +/-6.7 deg (libration), shifted by
    the site's distance from the pole.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sunchaser_data.horizons import sun_earth_for_site  # noqa: E402


def main():
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else -89.45
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 137.3
    elev = float(sys.argv[3]) if len(sys.argv) > 3 else 1850.0
    site = {"lat": lat, "lon": lon, "elevation_m": elev}

    s = sun_earth_for_site(site, "2027-01-01 00:00", "2027-12-31 23:00")
    n = len(s["times"])
    sun_el, earth_el = s["sun_elev_deg"], s["earth_elev_deg"]

    # Count full turns of the Sun's azimuth: unwrap removes the 360 -> 0 jumps.
    turns = abs(np.unwrap(np.radians(s["sun_az_deg"]))[-1] - np.radians(s["sun_az_deg"][0])) / (2 * np.pi)
    lunar_day_d = (n - 1) / 24 / turns

    print(f"Point lat {lat}, E-lon {lon}, elevation {elev} m ({90 + lat:.2f} deg from the pole)")
    print(f"Hours of data: {n} ({s['times'][0]} to {s['times'][-1]})")
    print(f"Sun elevation:   min {sun_el.min():6.2f}  max {sun_el.max():6.2f} deg")
    print(f"Earth elevation: min {earth_el.min():6.2f}  max {earth_el.max():6.2f} deg")
    print(f"Sun azimuth turns in the year: {turns:.2f} -> one lunar day = {lunar_day_d:.2f} days")
    print(f"Hours with the Sun's centre above a FLAT horizon: {100 * (sun_el > 0).mean():.1f}%")
    print(f"Hours with Earth's centre above a FLAT horizon:   {100 * (earth_el > 0).mean():.1f}%")

    pole_offset = 90 + lat
    swing = (earth_el.max() - earth_el.min()) / 2
    print(f"Earth half-swing: {swing:.2f} deg (expect roughly 6.7, give or take {pole_offset:.2f})")
    ok = (
        np.abs(sun_el).max() <= 1.6 + pole_offset      # Sun skims the horizon
        and 29.0 < lunar_day_d < 30.0                  # one turn per lunar day
        and 6.7 - 1.0 - pole_offset < swing < 6.7 + 1.0 + pole_offset  # libration
    )
    print("PASS: matches expected south-pole physics" if ok else "CHECK FAILED: look at the numbers above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
