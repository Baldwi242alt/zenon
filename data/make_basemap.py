"""Make the website's south-polar basemap from LOLA elevation data.

Run from the repo root:  python data/make_basemap.py

Reads the LOLA 80 m DEM (80 deg S to the pole, polar stereographic, 0 deg
longitude up), shades it as if lit from the upper left, tints it gently by
height, and writes web/src/assets/south_pole.jpg (1200 x 1200 px, about
507 m per pixel). Because the image is the DEM itself, a site's position on it
follows exactly from the projection formulas in sunchaser_data/dem.py; the
website uses the same formulas, so no calibration is needed.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))
from sunchaser_data.dem import PolarDEM  # noqa: E402

SIZE = 1200
OUT = ROOT / "web" / "src" / "assets" / "south_pole.jpg"


def main():
    dem = PolarDEM.from_cache("LDEM_80S_80M")
    n = dem.heights.shape[0]
    f = n // SIZE                                    # 7600 // 1200 = 6 -> 1266 px, trimmed below
    h = dem.heights[: f * (n // f), : f * (n // f)].reshape(n // f, f, n // f, f).mean(axis=(1, 3))
    h = np.array(Image.fromarray(h.astype(np.float32)).resize((SIZE, SIZE), Image.BILINEAR))
    px = 80.0 * n / SIZE                             # metres per output pixel
    gy, gx = np.gradient(h, px)
    az, alt = np.radians(315), np.radians(35)        # light from the upper left, 35 deg up
    slope = np.arctan(2.5 * np.hypot(gx, gy))        # exaggerate relief x2.5 for readability
    aspect = np.arctan2(-gx, gy)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(shade, 0, 1)
    z = np.clip((h - np.percentile(h, 2)) / (np.percentile(h, 98) - np.percentile(h, 2)), 0, 1)
    # Dark blue-grey lowlands to pale highlands, multiplied by the hillshade.
    lo, hi = np.array([22, 30, 46]), np.array([196, 202, 210])
    rgb = (lo[None, None, :] * (1 - z[..., None]) + hi[None, None, :] * z[..., None])
    rgb = rgb * (0.25 + 0.75 * shade[..., None])
    # Outside 80 deg S (corners beyond the DEM's circle) fade to the page colour.
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    r = np.hypot(xx - (SIZE - 1) / 2, yy - (SIZE - 1) / 2) / (SIZE / 2)
    fade = np.clip((r - 0.97) / 0.05, 0, 1)[..., None]
    rgb = rgb * (1 - fade) + np.array([11, 15, 23]) * fade
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).save(OUT, quality=82, optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
