"""LRO LOLA elevation maps (DEMs) of the lunar south pole.

Source: LOLA Gridded Data Records, polar stereographic, from the PDS
Geosciences node mirror at https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/
(for example LDEM_80S_80M.IMG: 80 m per pixel, 80 deg S to the pole).

File format (from the .LBL label that ships with each file):
  - raw 16-bit little-endian integers, LINES x LINE_SAMPLES
  - height in metres = DN * SCALING_FACTOR (0.5), relative to a sphere of
    radius 1737.4 km (the same reference Horizons uses)
  - polar stereographic projection on that sphere, centred on the south pole

Projection maths (spherical polar stereographic, south pole):
  r = 2R * tan(45 deg + lat/2)        distance from the pole on the map
  x = r * sin(lon),  y = r * cos(lon)  map metres, lon measured east
  sample (column) = SAMPLE_PROJECTION_OFFSET + x / MAP_SCALE
  line   (row)    = LINE_PROJECTION_OFFSET   - y / MAP_SCALE
So 0 deg longitude points UP the image and 90 deg E points RIGHT.
We confirmed this by sampling known features: Mons Mouton comes out at
+6.4 km and Shackleton's floor at -2.8 km; the flipped orientation gives
nonsense (Malapert at -2.6 km).

Simplification: stereographic maps are only exactly to scale at the pole.
At 84 deg S a map metre is about 0.3% larger than a ground metre; we ignore
this (it shifts horizon angles by well under 0.01 deg).
"""

import re
from pathlib import Path

import numpy as np

from .constants import MOON_RADIUS_M
from .horizon import bilinear_sample

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "lola"
BASE_URL = "https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/"


def parse_label(text):
    """Read the numbers we need from a PDS3 .LBL label."""

    def num(key):
        m = re.search(rf"^\s*{key}\s*=\s*([-+0-9.eE]+)", text, re.MULTILINE)
        if not m:
            raise ValueError(f"label has no {key}")
        return float(m.group(1))

    return {
        "lines": int(num("LINES")),
        "samples": int(num("LINE_SAMPLES")),
        "scaling": num("SCALING_FACTOR"),
        "map_scale_m": num("MAP_SCALE"),
        "line_offset": num("LINE_PROJECTION_OFFSET"),
        "sample_offset": num("SAMPLE_PROJECTION_OFFSET"),
        "radius_m": num("A_AXIS_RADIUS") * 1000.0,
        "center_lat": num("CENTER_LATITUDE"),
    }


class PolarDEM:
    """A LOLA south-polar DEM held in memory as heights in metres."""

    def __init__(self, img_path, lbl_path=None):
        img_path = Path(img_path)
        lbl_path = Path(lbl_path) if lbl_path else img_path.with_suffix(".LBL")
        self.meta = parse_label(lbl_path.read_text())
        if self.meta["center_lat"] != -90:
            raise ValueError("only south-polar DEMs are supported")
        raw = np.fromfile(img_path, dtype="<i2")
        expected = self.meta["lines"] * self.meta["samples"]
        if raw.size != expected:
            raise ValueError(f"{img_path.name}: {raw.size} values, label says {expected}")
        self.heights = (raw.reshape(self.meta["lines"], self.meta["samples"])
                        .astype(np.float32) * np.float32(self.meta["scaling"]))
        self.cell_size_m = self.meta["map_scale_m"]
        self.name = img_path.stem

    @classmethod
    def from_cache(cls, name="LDEM_80S_80M"):
        """Load a DEM previously downloaded to data/cache/lola/."""
        return cls(CACHE_DIR / f"{name}.IMG", CACHE_DIR / f"{name}.LBL")

    # ----- projection -----

    @staticmethod
    def latlon_to_xy(lat_deg, lon_deg, radius_m=MOON_RADIUS_M):
        """Latitude/east-longitude (degrees) to polar stereographic map metres."""
        lat = np.radians(np.asarray(lat_deg, dtype=float))
        lon = np.radians(np.asarray(lon_deg, dtype=float))
        r = 2.0 * radius_m * np.tan(np.pi / 4 + lat / 2)
        return r * np.sin(lon), r * np.cos(lon)

    @staticmethod
    def xy_to_latlon(x, y, radius_m=MOON_RADIUS_M):
        """Inverse of latlon_to_xy. Longitude returned in 0-360 east."""
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        r = np.hypot(x, y)
        lat = np.degrees(2.0 * np.arctan(r / (2.0 * radius_m))) - 90.0
        lon = np.mod(np.degrees(np.arctan2(x, y)), 360.0)
        return lat, lon

    def xy_to_rc(self, x, y):
        """Map metres to fractional (row, col) in the array (0-based)."""
        m = self.meta
        row = m["line_offset"] - np.asarray(y) / m["map_scale_m"]
        col = m["sample_offset"] + np.asarray(x) / m["map_scale_m"]
        return row, col

    def rc_to_xy(self, row, col):
        m = self.meta
        x = (np.asarray(col) - m["sample_offset"]) * m["map_scale_m"]
        y = (m["line_offset"] - np.asarray(row)) * m["map_scale_m"]
        return x, y

    def latlon_to_rc(self, lat_deg, lon_deg):
        return self.xy_to_rc(*self.latlon_to_xy(lat_deg, lon_deg))

    # ----- sampling -----

    def height_at(self, lat_deg, lon_deg):
        """Terrain height (m, relative to 1737.4 km) at a lat/lon, bilinear."""
        r, c = self.latlon_to_rc(np.atleast_1d(lat_deg), np.atleast_1d(lon_deg))
        h = bilinear_sample(self.heights, r, c)
        return float(h[0]) if np.ndim(lat_deg) == 0 else h

    def local_north_east_rc(self, lat_deg, lon_deg, step_m=50.0):
        """Unit vectors pointing local north and local east, in (row, col) steps.

        Worked out numerically: nudge the point a little north (and east) on
        the sphere, project both points, and see which way the map moved.
        That's safer near the pole than deriving it by hand.
        """
        dlat = np.degrees(step_m / MOON_RADIUS_M)
        dlon = dlat / max(np.cos(np.radians(lat_deg)), 1e-6)
        r0, c0 = self.latlon_to_rc(lat_deg, lon_deg)
        rn, cn = self.latlon_to_rc(lat_deg + dlat, lon_deg)
        re_, ce = self.latlon_to_rc(lat_deg, lon_deg + dlon)
        north = np.array([rn - r0, cn - c0], dtype=float)
        east = np.array([re_ - r0, ce - c0], dtype=float)
        return tuple(north / np.linalg.norm(north)), tuple(east / np.linalg.norm(east))
