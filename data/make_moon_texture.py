"""Moon texture for the website's 3D globe (equirectangular, 2048 x 1024).

South of 75 deg S the surface is real: shaded relief from LRO LOLA (LDEM_75S_120M), the
region Sunchaser studies. Elsewhere it is a procedural stand-in (craters and maria-like
tones), because only the polar map is bundled; the website says so.

Run from the repo root:  python data/make_moon_texture.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))
from sunchaser_data.dem import PolarDEM  # noqa: E402
from sunchaser_data.horizon import bilinear_sample  # noqa: E402

W, H = 2048, 1024
rng = np.random.default_rng(7)


def procedural():
    """Grey regolith with soft maria and a few thousand craters (rim light, floor shadow)."""
    lon = np.linspace(-np.pi, np.pi, W, endpoint=False)
    lat = np.linspace(np.pi / 2, -np.pi / 2, H)
    LON, LAT = np.meshgrid(lon, lat)
    tone = np.full((H, W), 0.62)
    for _ in range(9):                                     # maria: large dark smooth patches
        cl, cb, r = rng.uniform(-np.pi, np.pi), rng.uniform(-0.6, 0.9), rng.uniform(0.25, 0.6)
        d = np.arccos(np.clip(np.sin(LAT) * np.sin(cb) + np.cos(LAT) * np.cos(cb) * np.cos(LON - cl), -1, 1))
        tone -= 0.18 * np.exp(-(d / r) ** 2)
    noise = Image.fromarray((rng.random((H // 8, W // 8)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    tone += (np.asarray(noise) / 255.0 - 0.5) * 0.12
    shade = np.zeros((H, W))
    for _ in range(2600):                                  # craters, many small, few large
        r = rng.pareto(2.2) * 2.5 + 1.5
        if r > 60:
            continue
        cx, cy = rng.uniform(0, W), rng.uniform(0, H)
        x0, x1, y0, y1 = int(cx - 2 * r), int(cx + 2 * r) + 1, int(max(0, cy - 2 * r)), int(min(H, cy + 2 * r + 1))
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = np.hypot(xx - cx, yy - cy) / r
        bowl = np.where(d < 1, -(1 - d ** 2), 0.0) + np.where((d >= 1) & (d < 1.6), 0.35 * np.exp(-((d - 1.15) / 0.2) ** 2), 0.0)
        gx = np.gradient(bowl, axis=1)
        cols = np.mod(xx, W)
        np.add.at(shade, (yy, cols), gx * 0.9)
        np.add.at(tone, (yy, cols), np.where(d < 1, 0.04, 0.0))
    return np.clip(tone + shade, 0, 1)


def polar(img):
    """Replace 75-90 deg S with LOLA shaded relief, blended over the last 2 degrees."""
    dem = PolarDEM.from_cache("LDEM_75S_120M")
    lat = np.linspace(90, -90, H)
    lon = np.linspace(-180, 180, W, endpoint=False)
    rows = np.where(lat < -74)[0]
    LON, LAT = np.meshgrid(lon, lat[rows])
    r, c = dem.latlon_to_rc(LAT, LON)
    h = bilinear_sample(dem.heights, r, c)
    step = 120.0 * 6
    hx = bilinear_sample(dem.heights, r, c + 6) - h
    hy = bilinear_sample(dem.heights, r + 6, c) - h
    shade = np.clip(0.62 + (-hx + hy) / step * 2.2, 0, 1)
    shade = np.nan_to_num(shade, nan=0.6)
    w = np.clip((-LAT - 75) / 2.0, 0, 1)
    img[rows] = img[rows] * (1 - w) + shade * w
    return img


def main():
    img = polar(procedural())
    rgb = np.stack([img * 0.98, img * 0.97, img * 0.95], axis=-1)
    out = ROOT / "web" / "src" / "assets" / "moon.jpg"
    Image.fromarray((rgb * 255).astype(np.uint8)).filter(ImageFilter.SMOOTH).save(out, quality=84, optimize=True)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
