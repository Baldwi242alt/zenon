"""Real surface detail for the website's 3D terrain, from LRO LOLA 20 m elevation.

The shadow grids (shared/grid_SITE.json) are 64 x 64 cells of 80 m. To show the ground in more
detail without inventing anything, we cut the same 5.1 km square out of the 20 m LOLA map
(LDEM_80S_20M, 4 x finer) and keep only its local relief: elevation minus a 160 m-smoothed copy.
That high-pass image shows small craters, boulder fields and ridges as light/dark texture, with
no baked-in lighting direction (the website lights it with the real Sun direction instead).

We also save each grid's local north and east directions in grid (row, col) space, so the
website can turn a Sun azimuth from JPL Horizons into a direction on the grid.

Outputs: web/src/assets/relief/SITE.png (256 x 256, grey) and web/src/assets/relief/meta.json.
Run:  python data/make_relief.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))
from sunchaser_data.dem import PolarDEM  # noqa: E402
from sunchaser_data.horizon import bilinear_sample  # noqa: E402

OUT = ROOT / "web" / "src" / "assets" / "relief"
CELL_M, N = 80.0, 64            # must match build_grid.py
PX = 256                        # texture size: 20 m pixels across the grid's cell centres


def box_blur(a, r):
    """Mean filter of radius r (in pixels), by cumulative sums; edges use the available pixels."""
    pad = np.pad(a, r, mode="edge")
    c = pad.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    k = 2 * r + 1
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def main():
    dem = PolarDEM.from_cache("LDEM_80S_20M", lazy=True)
    sites = json.loads((ROOT / "shared" / "sites.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    k = CELL_M / dem.cell_size_m                         # DEM pixels per grid cell (4)
    for s in sites:
        rc_r, rc_c = dem.latlon_to_rc(s["lat"], s["lon"])
        block, r0, c0 = dem.window(s["lat"], s["lon"], (N / 2 + 4) * CELL_M)
        # Texture spans the first to the last grid-cell centre, like the 3D mesh does.
        span = (N - 1) / 2 * k
        t = np.linspace(-span, span, PX)
        rr = rc_r - r0 + t[:, None] + 0 * t[None, :]
        cc = rc_c - c0 + 0 * t[:, None] + t[None, :]
        h = bilinear_sample(block, rr, cc)
        relief = h - box_blur(h, 4)                      # remove features wider than ~160 m
        lim = np.percentile(np.abs(relief), 98) or 1.0
        img = np.clip(128 + 110 * relief / lim, 0, 255).astype(np.uint8)
        Image.fromarray(img, "L").save(OUT / f"{s['id']}.png", optimize=True)
        north, east = dem.local_north_east_rc(s["lat"], s["lon"])
        meta[s["id"]] = {"north_rc": [round(float(v), 6) for v in north], "east_rc": [round(float(v), 6) for v in east],
                         "source": "LRO LOLA LDEM_80S_20M, high-pass relief"}
        print(s["id"], "relief range ±%.1f m" % lim)
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
