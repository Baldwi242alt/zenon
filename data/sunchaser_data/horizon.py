"""Terrain horizon by ray casting, including lunar curvature.

For an observer standing on the terrain, the "horizon" in a given compass
direction (azimuth) is the highest angle at which terrain blocks the sky
in that direction. If the Sun is below that angle, the observer is in shadow.

How it works, for each azimuth:
  1. Walk outward from the observer along that direction.
  2. At each distance d, read the terrain height h there.
  3. The Moon curves away beneath a straight line of sight, so distant
     ground is lower than the map says by about d^2 / (2R).
  4. The angle to that point is atan((h - drop - observer_height) / d).
  5. The horizon is the largest angle found along the walk.

This module works on a DEM stored as a 2D numpy array on a regular grid
(cell_size_m apart). Directions are given as unit vectors in (row, col)
space, so the caller decides which way is north. That keeps the maths
here independent of any map projection.
"""

import numpy as np

from .constants import DEFAULT_MAST_M, MOON_RADIUS_M


def curvature_drop_m(distance_m):
    """How far the lunar surface falls below a flat tangent line at a distance.

    drop = d^2 / (2R). About 29 m at 10 km and 720 m at 50 km.
    (This is the small-angle approximation; it's accurate to better than
    0.1% for distances under 100 km.)
    """
    d = np.asarray(distance_m, dtype=float)
    return d * d / (2.0 * MOON_RADIUS_M)


def bilinear_sample(dem, rows, cols):
    """Sample a 2D elevation array at fractional (row, col) positions.

    Points outside the array return NaN, so callers can ignore them.
    Bilinear = a weighted average of the four surrounding cells, which
    avoids the stair-step artefacts of just taking the nearest cell.
    """
    rows = np.asarray(rows, dtype=float)
    cols = np.asarray(cols, dtype=float)
    n_rows, n_cols = dem.shape
    inside = (rows >= 0) & (rows <= n_rows - 1) & (cols >= 0) & (cols <= n_cols - 1)
    r = np.clip(rows, 0, n_rows - 1)
    c = np.clip(cols, 0, n_cols - 1)
    r0 = np.minimum(np.floor(r).astype(int), n_rows - 2) if n_rows > 1 else np.zeros_like(r, int)
    c0 = np.minimum(np.floor(c).astype(int), n_cols - 2) if n_cols > 1 else np.zeros_like(c, int)
    fr = r - r0
    fc = c - c0
    r1 = np.minimum(r0 + 1, n_rows - 1)
    c1 = np.minimum(c0 + 1, n_cols - 1)
    top = dem[r0, c0] * (1 - fc) + dem[r0, c1] * fc
    bottom = dem[r1, c0] * (1 - fc) + dem[r1, c1] * fc
    out = top * (1 - fr) + bottom * fr
    return np.where(inside, out, np.nan)


def horizon_profile(
    dem,
    cell_size_m,
    row,
    col,
    azimuths_deg,
    north_rc=(-1.0, 0.0),
    east_rc=(0.0, 1.0),
    max_distance_m=None,
    mast_m=DEFAULT_MAST_M,
    step_cells=0.5,
    distances_m=None,
):
    """Horizon elevation angle (degrees) for each azimuth, seen from one cell.

    dem            2D array of terrain heights in metres
    cell_size_m    spacing between cells in metres
    row, col       observer position (may be fractional)
    azimuths_deg   1D array of azimuths, measured from north through east
    north_rc       unit vector pointing local north, in (row, col) steps
    east_rc        unit vector pointing local east, in (row, col) steps
                   (defaults: north = up the array, east = right)
    max_distance_m how far to look; defaults to the edge of the DEM
    mast_m         observer height above the ground
    step_cells     sampling step along each ray, in cells
    distances_m    optional explicit sample distances (overrides max_distance_m
                   and step_cells); use far_field_distances() for long rays

    Returns an array the same length as azimuths_deg. A direction with no
    terrain inside the DEM returns -90 (nothing blocks the sky there).

    Simplification: terrain beyond the DEM edge is ignored. For real sites
    the caller must supply a DEM large enough (about 150 km) that distant
    mountains are included, since they set the horizon for a low Sun.
    """
    dem = np.asarray(dem, dtype=float)
    az = np.radians(np.asarray(azimuths_deg, dtype=float))
    n_rows, n_cols = dem.shape
    if max_distance_m is None:
        max_distance_m = np.hypot(n_rows, n_cols) * cell_size_m

    # Distances along each ray, starting one step out (the observer's own
    # cell would give a meaningless angle).
    if distances_m is None:
        dists_cells = np.arange(step_cells, max_distance_m / cell_size_m + step_cells, step_cells)
        dists_m = dists_cells * cell_size_m
    else:
        dists_m = np.asarray(distances_m, dtype=float)
        dists_cells = dists_m / cell_size_m

    # Observer eye height: ground at the observer plus the mast.
    h0 = float(bilinear_sample(dem, np.array([row]), np.array([col]))[0]) + mast_m

    # Direction of each azimuth in (row, col) space:
    # direction = cos(az) * north + sin(az) * east
    dir_r = np.cos(az)[:, None] * north_rc[0] + np.sin(az)[:, None] * east_rc[0]
    dir_c = np.cos(az)[:, None] * north_rc[1] + np.sin(az)[:, None] * east_rc[1]

    # Every sample point for every azimuth at once (shape: n_az x n_dist).
    sample_r = row + dir_r * dists_cells[None, :]
    sample_c = col + dir_c * dists_cells[None, :]
    heights = bilinear_sample(dem, sample_r, sample_c)

    drop = curvature_drop_m(dists_m)[None, :]
    angles = np.degrees(np.arctan2(heights - drop - h0, dists_m[None, :]))
    angles = np.where(np.isnan(angles), -90.0, angles)
    return angles.max(axis=1)


def far_field_distances(cell_size_m, near_m=20_000.0, max_m=150_000.0, growth=0.01):
    """Sample distances for long rays: every cell out to near_m, then sparser.

    Close terrain needs fine sampling (a small hill nearby matters a lot);
    far terrain only matters if it's big, so beyond near_m each step grows
    by `growth` (1%) of the distance. This keeps a 150 km ray to a few
    hundred samples instead of ~2,000.
    """
    near = np.arange(cell_size_m, near_m + cell_size_m, cell_size_m)
    far = [near[-1]]
    while far[-1] < max_m:
        far.append(far[-1] * (1.0 + growth))
    return np.concatenate([near, np.array(far[1:])])


def interp_horizon(profile_deg, profile_az_deg, query_az_deg):
    """Horizon height at any azimuth, interpolated from a sampled profile.

    Wraps around 360 degrees, so an azimuth of 359.9 is interpolated
    between the last bin and the first one.
    """
    az = np.asarray(profile_az_deg, dtype=float)
    prof = np.asarray(profile_deg, dtype=float)
    az_wrapped = np.concatenate([az, [az[0] + 360.0]])
    prof_wrapped = np.concatenate([prof, [prof[0]]])
    q = np.mod(np.asarray(query_az_deg, dtype=float) - az[0], 360.0) + az[0]
    return np.interp(q, az_wrapped, prof_wrapped)
