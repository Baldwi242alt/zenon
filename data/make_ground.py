"""Real orbital imagery of the ground under each site's 3D terrain.

For each site we cut the exact 5.1 km square of its shadow grid (shared/grid_SITE.json) out of a
NASA LROC mosaic served by NASA Moon Trek (trek.nasa.gov), so the 3D model is draped with a
photograph of the actual ground:

  * LRO_NAC_AvgMosaic_SPole855_1mp: LROC Narrow Angle Camera mosaic of the south pole to 85.5 S
    (about 1 m/pixel; we use the 4.2 m/pixel zoom level).
  * LRO_WAC_Mosaic_SPole60_100mp: LROC Wide Angle Camera mosaic, used for sites outside the
    NAC mosaic (about 100 m/pixel, so those textures are soft).

Both mosaics and our LOLA grids use the same south polar stereographic projection (x = r sin lon,
y = r cos lon, Moon radius 1737.4 km), so every texture pixel maps to the mosaic exactly:
grid cell -> LOLA (row, col) -> map metres (x, y) -> mosaic pixel.

Outputs: web/src/assets/ground/SITE.jpg and web/src/assets/ground/sources.json.
Run:  python data/make_ground.py
"""
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))
from sunchaser_data.dem import PolarDEM  # noqa: E402
from sunchaser_data.horizon import bilinear_sample  # noqa: E402

OUT = ROOT / "web" / "src" / "assets" / "ground"
CACHE = ROOT / "data" / "cache" / "trek"
CELL_M, N = 80.0, 64           # must match build_grid.py
TRek = "https://trek.nasa.gov/tiles/Moon/SP/"
LAYER, ZOOM = "LRO_NAC_AvgMosaic_SPole855_1mp", 11   # LROC NAC south-pole mosaic, 4.2 m/pixel level


def matrix(layer):
    """Tile matrices of a layer: {zoom: (metres_per_pixel, left_x, top_y, tile_px)}."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{layer}_caps.xml"
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(f"{TRek}{layer}/1.0.0/WMTSCapabilities.xml", timeout=60).read())
    s = path.read_text()
    out = {}
    for b in re.findall(r"<TileMatrix>(.*?)</TileMatrix>", s, re.S):
        g = lambda t: re.search(f"<{t}>([^<]*)</{t}>", b).group(1)  # noqa: E731
        left, top = map(float, g("TopLeftCorner").split())
        out[int(g("ows:Identifier"))] = (float(g("ScaleDenominator")) * 0.00028, left, top, int(g("TileWidth")))
    return out


def tile(layer, z, r, c):
    path = CACHE / layer / f"{z}_{r}_{c}.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(urllib.request.urlopen(f"{TRek}{layer}/1.0.0/default/default028mm/{z}/{r}/{c}.png", timeout=60).read())
        except Exception:
            return None
    try:
        im = Image.open(path).convert("LA")
    except Exception:
        return None
    a = np.asarray(im, dtype=np.float32)
    out = a[..., 0].copy()
    out[a[..., 1] == 0] = np.nan          # transparent = outside the mosaic
    return out


def main():
    dem = PolarDEM.from_cache("LDEM_80S_20M", lazy=True)
    sites = json.loads((ROOT / "shared" / "sites.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {}
    for s in sites:
        rc_r, rc_c = dem.latlon_to_rc(s["lat"], s["lon"])
        cx, cy = dem.rc_to_xy(rc_r, rc_c)
        res, left, top, tp = matrix(LAYER)[ZOOM]
        # Texture pixels span the first to the last grid-cell centre (like the 3D mesh).
        k = CELL_M / dem.cell_size_m
        span = (N - 1) / 2 * k
        t = np.linspace(-span, span, 1024)
        x, y = dem.rc_to_xy(rc_r + t[:, None] + 0 * t[None, :], rc_c + 0 * t[:, None] + t[None, :])
        mx, my = (x - left) / res, (top - y) / res            # mosaic pixel coordinates
        r0, r1 = int(my.min() // tp), int(my.max() // tp)
        c0, c1 = int(mx.min() // tp), int(mx.max() // tp)
        block = np.full(((r1 - r0 + 1) * tp, (c1 - c0 + 1) * tp), np.nan, dtype=np.float32)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                a = tile(LAYER, ZOOM, r, c)
                if a is not None:
                    block[(r - r0) * tp:(r - r0) * tp + a.shape[0], (c - c0) * tp:(c - c0) * tp + a.shape[1]] = a
        img = bilinear_sample(block, my - r0 * tp, mx - c0 * tp)
        covered = np.isfinite(img)
        # Outside the NAC mosaic (beyond about 85.5 S) fill with real LOLA 20 m relief (make_relief.py),
        # matched to the photo's brightness where both exist.
        rel = np.asarray(Image.open(ROOT / "web" / "src" / "assets" / "relief" / f"{s['id']}.png").resize((1024, 1024), Image.BILINEAR), dtype=np.float32)
        if covered.any():
            ref = img[covered]
            fill = (rel - rel.mean()) / (rel.std() or 1) * ref.std() * 0.8 + ref.mean()
        else:
            fill = rel
        img = np.where(covered, img, fill)
        lo, hi = np.percentile(img, 1), np.percentile(img, 99.5)   # gentle contrast stretch
        img = np.clip((img - lo) / max(hi - lo, 1) * 255, 0, 255).astype(np.uint8)
        Image.fromarray(img, "L").save(OUT / f"{s['id']}.jpg", quality=82)
        share = float(covered.mean())
        sources[s["id"]] = {"nac_coverage": round(share, 3), "photo": f"{LAYER} (LROC NAC, {res:.1f} m/px)" if share else None,
                            "fill": "LRO LOLA LDEM_80S_20M relief" if share < 1 else None}
        print(s["id"], f"NAC coverage {100 * share:.0f}%")
    (OUT / "sources.json").write_text(json.dumps(sources, indent=1))


if __name__ == "__main__":
    main()
