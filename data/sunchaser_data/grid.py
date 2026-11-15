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
    once per block of 8 x 8 cells (from the block's middle cell); each cell
    then works out its own angle to that terrain from its own ground height.
    (A cell is at most a few hundred metres from its block's anchor, small
    next to 15+ km, so the rays are effectively the same.)
  - The horizon is the higher of the two.

The Sun's direction comes from the site's timeline (JPL Horizons at the
centre), corrected per cell in two ways: the Moon curves away under the
grid, so a cell d metres closer to the Sun sees it higher by d / R radians
(about 0.03 deg per km); and local north turns with longitude near the pole,
so the Sun's azimuth in a cell is shifted by the longitude difference from
the centre (a few degrees across a 5 km grid).

Honest limits: azimuths are sampled every 1 deg; far-field rays are cast
per block of cells, not from each cell; observer is a 2 m mast; features
smaller than a cell are smoothed out.
"""

import numpy as np

from .constants import DEFAULT_MAST_M, MOON_RADIUS_M
from .horizon import bilinear_sample, curvature_drop_m, far_field_distances, horizon_profile
from .sunfrac import sun_visible_fraction

GRID_AZ = np.arange(0.0, 360.0, 1.0)
NEAR_M = 15_000.0
FAR_M = 150_000.0
FAR_BLOCK = 8          # far-field rays are cast once per block of 8 x 8 cells


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

        # --- far-field terrain: rays cast from an anchor in each block of cells ---
        # Distant terrain (15-150 km) looks almost the same from cells a few hundred
        # metres apart, so rays are cast once per block of FAR_BLOCK x FAR_BLOCK cells
        # (from the block's middle cell, with that cell's own north), and every cell in
        # the block works out its own angle to that terrain from its own ground height.
        fd = far_field_distances(far_dem.cell_size_m, max_m=FAR_M)
        fd = fd[fd >= NEAR_M]
        az = np.radians(GRID_AZ)
        steps = fd[None, :] / far_dem.cell_size_m
        drop = curvature_drop_m(fd)[None, :]
        self.far_h = np.empty((rows, cols, GRID_AZ.size))
        for i0 in range(0, rows, FAR_BLOCK):
            for j0 in range(0, cols, FAR_BLOCK):
                i1, j1 = min(i0 + FAR_BLOCK, rows), min(j0 + FAR_BLOCK, cols)
                a_lat = self.cell_lat[(i0 + i1 - 1) // 2, (j0 + j1 - 1) // 2]
                a_lon = self.cell_lon[(i0 + i1 - 1) // 2, (j0 + j1 - 1) // 2]
                fr, fc = far_dem.latlon_to_rc(a_lat, a_lon)
                fn, fe = far_dem.local_north_east_rc(a_lat, a_lon)
                dr = np.cos(az)[:, None] * fn[0] + np.sin(az)[:, None] * fe[0]
                dc = np.cos(az)[:, None] * fn[1] + np.sin(az)[:, None] * fe[1]
                ray_h = bilinear_sample(far_dem.heights, fr + dr * steps, fc + dc * steps) - drop
                eye = (self.elevation[i0:i1, j0:j1] + mast_m).reshape(-1)
                ang = np.degrees(np.arctan2(ray_h[None, :, :] - eye[:, None, None], fd[None, None, :]))
                far = np.nanmax(np.where(np.isnan(ang), -90.0, ang), axis=2)
                self.far_h[i0:i1, j0:j1] = far.reshape(i1 - i0, j1 - j0, GRID_AZ.size)

        self.horizon = np.maximum(self.near_h, self.far_h)        # (rows, cols, az)

        # Local north turns with longitude near the pole, so the Sun's compass direction
        # differs from cell to cell: azimuth in a cell = azimuth at the centre + (centre
        # longitude - cell longitude). Up to a few degrees across a 5 km grid.
        self.az_shift = ((lon - self.cell_lon + 180.0) % 360.0) - 180.0

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
            # Horizon at the Sun's azimuth as each cell sees it: linear interpolation
            # between the 1 deg bins of that cell's own horizon profile.
            pos = (az[s] + self.az_shift) % 360.0
            k0 = np.floor(pos).astype(int) % 360
            k1 = (k0 + 1) % 360
            w = pos - np.floor(pos)
            h0 = np.take_along_axis(self.horizon, k0[:, :, None], axis=2)[:, :, 0]
            h1 = np.take_along_axis(self.horizon, k1[:, :, None], axis=2)[:, :, 0]
            hz = h0 * (1 - w) + h1 * w
            out[s] = np.rint(100 * sun_visible_fraction(el_cell, hz))
        return out
