"""Shadow grid: per-cell sunlight over a small area around a site (schema 2.3).

The grid is rows x cols cells of cell_size_m, centred on the site and
aligned with the LOLA polar map (rows run top to bottom, columns left to
right, 0 deg longitude points up), so it lines up with the south-polar map
image on the website.

For every cell we need its terrain horizon in every direction. Doing a
full 150 km ray cast from each of 4,096 cells would be slow, so we split it
(handbook B.11):
  - NEAR field (within 15 km): ray-cast separately from every cell on the
    LOLA 20 m DEM, because nearby hills look completely different from
    cells a few hundred metres apart.
  - FAR field (15 to 150 km): the terrain heights along each ray are read
    once from the grid centre; each cell then works out its own angle to
    that terrain from its own ground height. (A cell is at most 1.8 km from
    the centre, small next to 15+ km, so the rays are effectively the same.)
  - The horizon is the higher of the two.

The Sun's direction comes from the site's timeline (JPL Horizons at the
centre). The Moon curves away under the grid, so a cell d metres closer to
the Sun sees it higher by d / R radians (about 0.03 deg per km); we apply
that correction per cell.

Honest limits: azimuths are sampled every 1 deg; far-field rays are cast
from the centre, not from each cell; observer is a 2 m mast; cells are
40 m, so features smaller than that are smoothed out.
"""

import numpy as np

from .constants import DEFAULT_MAST_M, MOON_RADIUS_M
from .horizon import bilinear_sample, curvature_drop_m, far_field_distances, horizon_profile
from .sunfrac import sun_visible_fraction

GRID_AZ = np.arange(0.0, 360.0, 1.0)
NEAR_M = 15_000.0
FAR_M = 150_000.0


def near_distances(cell_m, fine_to_m=3_000.0, max_m=NEAR_M, growth=0.01):
    """Every DEM cell out to 3 km, then steps growing by 1% of the distance."""
    return far_field_distances(cell_m, near_m=fine_to_m, max_m=max_m, growth=growth)


class ShadowGrid:
    """Terrain, slopes and per-cell horizons for one site's grid."""

    def __init__(self, near_dem, far_dem, lat, lon, rows=64, cols=64, cell_size_m=40.0,
                 mast_m=DEFAULT_MAST_M):
        self.lat, self.lon = lat, lon
        self.rows, self.cols, self.cell = rows, cols, cell_size_m
        self.mast = mast_m

        # --- cell centres in the 20 m DEM's (row, col) space ---
        k = cell_size_m / near_dem.cell_size_m                 # DEM pixels per grid cell
        rc_r, rc_c = near_dem.latlon_to_rc(lat, lon)
        gi = (np.arange(rows) - (rows - 1) / 2) * k
        gj = (np.arange(cols) - (cols - 1) / 2) * k
        cell_r = rc_r + gi[:, None] + 0 * gj[None, :]
        cell_c = rc_c + 0 * gi[:, None] + gj[None, :]

        block, r0, c0 = near_dem.window(lat, lon, NEAR_M + max(rows, cols) * cell_size_m)
        self._block, self._r0, self._c0 = block, r0, c0
        br, bc = cell_r - r0, cell_c - c0

        # --- elevation: average of the DEM over each 40 m cell ---
        # Sample a k x k pattern inside each cell and average (k = 2 for 20 m -> 40 m).
        offs = (np.arange(int(round(k))) - (int(round(k)) - 1) / 2)
        samples = [bilinear_sample(block, br + a, bc + b) for a in offs for b in offs]
        self.elevation = np.mean(samples, axis=0)

        # --- slope: steepest gradient, from central differences ---
        gy, gx = np.gradient(self.elevation, cell_size_m)
        self.slope = np.degrees(np.arctan(np.hypot(gx, gy)))

        # --- local north/east (unit vectors in row/col space) per cell ---
        x, y = near_dem.rc_to_xy(cell_r, cell_c)
        self.cell_lat, self.cell_lon = near_dem.xy_to_latlon(x, y)
        self.north_c, self.east_c = near_dem.local_north_east_rc(lat, lon)

        # --- near-field horizons, one ray cast per cell ---
        nd = near_distances(near_dem.cell_size_m)
        self.near_h = np.empty((rows, cols, GRID_AZ.size))
        for i in range(rows):
            for j in range(cols):
                n_rc, e_rc = near_dem.local_north_east_rc(self.cell_lat[i, j], self.cell_lon[i, j])
                self.near_h[i, j] = horizon_profile(
                    block, near_dem.cell_size_m, br[i, j], bc[i, j], GRID_AZ,
                    north_rc=n_rc, east_rc=e_rc, distances_m=nd, mast_m=mast_m,
                    ground_h_m=self.elevation[i, j])

        # --- far-field terrain along rays from the centre, then per-cell angles ---
        fr, fc = far_dem.latlon_to_rc(lat, lon)
        fn, fe = far_dem.local_north_east_rc(lat, lon)
        fd = far_field_distances(far_dem.cell_size_m, max_m=FAR_M)
        fd = fd[fd >= NEAR_M]
        az = np.radians(GRID_AZ)
        dr = np.cos(az)[:, None] * fn[0] + np.sin(az)[:, None] * fe[0]
        dc = np.cos(az)[:, None] * fn[1] + np.sin(az)[:, None] * fe[1]
        steps = fd[None, :] / far_dem.cell_size_m
        ray_h = bilinear_sample(far_dem.heights, fr + dr * steps, fc + dc * steps)
        ray_h = ray_h - curvature_drop_m(fd)[None, :]           # (az, dist)
        eye = (self.elevation + mast_m).reshape(-1)               # (cells,)
        far = np.empty((eye.size, GRID_AZ.size))
        for s in range(0, eye.size, 256):                         # chunks keep memory small
            e = eye[s:s + 256, None, None]
            ang = np.degrees(np.arctan2(ray_h[None, :, :] - e, fd[None, None, :]))
            far[s:s + 256] = np.nanmax(np.where(np.isnan(ang), -90.0, ang), axis=2)
        self.far_h = far.reshape(rows, cols, GRID_AZ.size)

        self.horizon = np.maximum(self.near_h, self.far_h)        # (rows, cols, az)

        # Offsets of each cell from the centre, in metres north and east.
        off_r = (cell_r - rc_r) * near_dem.cell_size_m
        off_c = (cell_c - rc_c) * near_dem.cell_size_m
        self.off_north = off_r * self.north_c[0] + off_c * self.north_c[1]
        self.off_east = off_r * self.east_c[0] + off_c * self.east_c[1]

    def sun_pct(self, sun_az_deg, sun_elev_deg):
        """Percent of the Sun's disk visible from every cell, for each time step.

        sun_az_deg, sun_elev_deg: arrays (one value per step) at the grid centre.
        Returns an int array (steps, rows, cols) with values 0-100.
        """
        az = np.asarray(sun_az_deg, dtype=float)
        el = np.asarray(sun_elev_deg, dtype=float)
        out = np.empty((az.size, self.rows, self.cols), dtype=np.int16)
        for s in range(az.size):
            a = np.radians(az[s])
            # Cells closer to the Sun see it slightly higher (lunar curvature).
            toward_sun_m = self.off_north * np.cos(a) + self.off_east * np.sin(a)
            el_cell = el[s] + np.degrees(toward_sun_m / MOON_RADIUS_M)
            # Horizon at the Sun's azimuth: linear interpolation between 1 deg bins.
            pos = (az[s] % 360.0)
            k0 = int(np.floor(pos)) % 360
            k1 = (k0 + 1) % 360
            w = pos - np.floor(pos)
            hz = self.horizon[:, :, k0] * (1 - w) + self.horizon[:, :, k1] * w
            out[s] = np.rint(100 * sun_visible_fraction(el_cell, hz))
        return out
