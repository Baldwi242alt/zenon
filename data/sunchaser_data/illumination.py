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


NEAR_M = 15_000.0   # switch from the sharp near DEM to the wide far DEM here
FAR_M = 150_000.0   # distant mountains matter for a Sun this low


def _ray_end_inside(dem, row, col, north, east, dist_m):
    """Fraction of the 720 rays whose end point is still on this DEM."""
    az = np.radians(PROFILE_AZ)
    end_r = row + (np.cos(az) * north[0] + np.sin(az) * east[0]) * dist_m / dem.cell_size_m
    end_c = col + (np.cos(az) * north[1] + np.sin(az) * east[1]) * dist_m / dem.cell_size_m
    n_r, n_c = dem.shape
    inside = (end_r >= 0) & (end_r <= n_r - 1) & (end_c >= 0) & (end_c <= n_c - 1)
    return float(inside.mean())


def horizon_for_point(far_dem, lat, lon, near_dem=None, near_m=NEAR_M, max_m=FAR_M,
                      mast_m=DEFAULT_MAST_M):
    """Terrain horizon (deg) in 720 directions around a point, plus coverage.

    Two resolutions (handbook B.7):
      - near_dem (e.g. LOLA 20 m) for terrain within near_m, where small
        bumps matter;
      - far_dem (e.g. LOLA 120 m to 75 S) for terrain from near_m to max_m,
        where only big mountains matter but the map must reach far enough.
    The horizon in each direction is the higher of the two. The observer's
    ground height comes from the sharpest DEM available.
    Without near_dem, far_dem is used for the whole ray.

    Returns (profile_deg, coverage, ground_h_m). Coverage is the fraction of
    directions whose ray stays on far_dem for the full max_m; below 1.0
    means some distant terrain was missing.
    """
    sharp = near_dem if near_dem is not None else far_dem
    ground_h = sharp.height_at(lat, lon)

    # Far field: the big DEM, from near_m (or from the first cell) to max_m.
    row, col = far_dem.latlon_to_rc(lat, lon)
    north, east = far_dem.local_north_east_rc(lat, lon)
    dists = far_field_distances(far_dem.cell_size_m, max_m=max_m)
    if near_dem is not None:
        dists = dists[dists >= near_m]
    prof = horizon_profile(far_dem.heights, far_dem.cell_size_m, float(row), float(col), PROFILE_AZ,
                           north_rc=north, east_rc=east, distances_m=dists, mast_m=mast_m,
                           ground_h_m=ground_h)
    coverage = _ray_end_inside(far_dem, row, col, north, east, max_m)

    # Near field: a square of the sharp DEM around the point.
    if near_dem is not None:
        block, r0, c0 = near_dem.window(lat, lon, near_m)
        nrow, ncol = near_dem.latlon_to_rc(lat, lon)
        nnorth, neast = near_dem.local_north_east_rc(lat, lon)
        near_d = np.arange(near_dem.cell_size_m, near_m + near_dem.cell_size_m, near_dem.cell_size_m)
        near_prof = horizon_profile(block, near_dem.cell_size_m, float(nrow - r0), float(ncol - c0),
                                    PROFILE_AZ, north_rc=nnorth, east_rc=neast, distances_m=near_d,
                                    mast_m=mast_m, ground_h_m=ground_h)
        prof = np.maximum(prof, near_prof)
    return prof, coverage, ground_h


def load_standard_dems():
    """The DEM pair used for real sites: LOLA 20 m (near) and 120 m to 75 S (far)."""
    from .dem import PolarDEM
    return PolarDEM.from_cache("LDEM_80S_20M", lazy=True), PolarDEM.from_cache("LDEM_75S_120M")


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
