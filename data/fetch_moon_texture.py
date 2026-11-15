"""Build the website's Moon globe texture from real NASA imagery.

Source: NASA Moon Trek (trek.nasa.gov), layer LRO_WAC_Mosaic_Global_303ppd_v02, the Lunar
Reconnaissance Orbiter Camera wide-angle global mosaic (NASA/GSFC/Arizona State University).
Zoom level 3 of its equirectangular tile grid is 16 x 8 tiles of 256 px = 4096 x 2048 px; we stitch
it and save a 2048 x 1024 JPEG (longitude -180..180 left to right, latitude 90..-90 top to bottom),
which is the layout three.js expects for a sphere texture.

Run:  python data/fetch_moon_texture.py   (writes web/src/assets/moon.jpg)
"""
import io
import urllib.request
from pathlib import Path

from PIL import Image

BASE = "https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm"
ZOOM, ROWS, COLS, TILE = 3, 8, 16, 256
OUT = Path(__file__).resolve().parents[1] / "web" / "src" / "assets" / "moon.jpg"


def main() -> None:
    mosaic = Image.new("L", (COLS * TILE, ROWS * TILE))
    for r in range(ROWS):
        for c in range(COLS):
            with urllib.request.urlopen(f"{BASE}/{ZOOM}/{r}/{c}.jpg", timeout=30) as resp:
                mosaic.paste(Image.open(io.BytesIO(resp.read())).convert("L"), (c * TILE, r * TILE))
    mosaic.resize((2048, 1024), Image.LANCZOS).save(OUT, quality=85)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
