"""Terrain-aware Sun and Earth visibility at one point, hour by hour.

Combines the three building blocks:
  1. horizon_for_point: the terrain horizon all around the point, by ray
     casting across a LOLA DEM out to 150 km (with lunar curvature);
  2. Horizons: where the Sun and Earth are every hour;
  3. sunfrac: how much of the Sun's disk clears the horizon.

The result is used to choose sites (stage 3) and to write the timeline
files (stage 5).
"""

import numpy as np

from .constants import DEFAULT_MAST_M
from .horizon import far_field_distances, horizon_profile, interp_horizon
from .horizons import sun_earth_for_site
from .metrics import SUNLIT_THRESHOLD, longest_run
from .sunfrac import sun_visible_fraction

PROFILE_AZ = np.arange(0.0, 360.0, 0.5)  # 720 directions, 0.5 deg apart


def horizon_for_point(dem, lat, lon, max_m=150_000.0, mast_m=DEFAULT_MAST_M):
    """Terrain horizon (deg) in 720 directions around a point, plus coverage.

    Coverage is the fraction of directions whose ray stayed inside the DEM
    for the full max_m. Below 1.0 means some distant terrain was missing
    (for points near the DEM's 80 deg S edge), so the horizon there may be
    slightly too low.
    """
    row, col = dem.latlon_to_rc(lat, lon)
    north, east = dem.local_north_east_rc(lat, lon)
    dists = far_field_distances(dem.cell_size_m, max_m=max_m)
    prof = horizon_profile(dem.heights, dem.cell_size_m, float(row), float(col), PROFILE_AZ,
                           north_rc=north, east_rc=east, distances_m=dists, mast_m=mast_m)
    # Coverage check: is the end of each ray still on the map?
    az = np.radians(PROFILE_AZ)
    end_r = row + (np.cos(az) * north[0] + np.sin(az) * east[0]) * max_m / dem.cell_size_m
    end_c = col + (np.cos(az) * north[1] + np.sin(az) * east[1]) * max_m / dem.cell_size_m
    n_r, n_c = dem.heights.shape
    inside = (end_r >= 0) & (end_r <= n_r - 1) & (end_c >= 0) & (end_c <= n_c - 1)
    return prof, float(inside.mean())


def light_series(site, profile_deg, start, stop):
    """Hourly Sun/Earth geometry and visibility for a site with a known horizon."""
    s = sun_earth_for_site(site, start, stop)
    sun_hz = interp_horizon(profile_deg, PROFILE_AZ, s["sun_az_deg"])
    earth_hz = interp_horizon(profile_deg, PROFILE_AZ, s["earth_az_deg"])
    s["sun_horizon_deg"] = sun_hz
    s["earth_horizon_deg"] = earth_hz
    s["sun_frac"] = sun_visible_fraction(s["sun_elev_deg"], sun_hz)
    s["earth_visible"] = s["earth_elev_deg"] > earth_hz
    return s


def summarise(series):
    """Headline percentages for a series (used to compare candidate points)."""
    lit = series["sun_frac"] >= SUNLIT_THRESHOLD
    earth = series["earth_visible"]
    return {
        "sunlit_pct": 100.0 * lit.mean(),
        "earth_pct": 100.0 * earth.mean(),
        "both_pct": 100.0 * (lit & earth).mean(),
        "longest_dark_h": float(longest_run(~lit)),
        "longest_no_earth_h": float(longest_run(~earth)),
    }
