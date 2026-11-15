"""JPL Horizons client: where the Sun and Earth sit in the sky at a lunar site.

JPL Horizons (https://ssd.jpl.nasa.gov/api/horizons.api) is NASA's
ephemeris service, built on the DE441 planetary ephemeris. We ask it, for
an observer standing at a given latitude/longitude/height on the Moon,
"what are the azimuth and elevation of the Sun (and of Earth) every hour?"

Key query parameters (documented at https://ssd-api.jpl.nasa.gov/doc/horizons.html):
  COMMAND='10'        target body: 10 = Sun, 399 = Earth, 301 = Moon
  CENTER='coord@301'  observer on the surface of body 301 (the Moon)
  COORD_TYPE='GEODETIC', SITE_COORD='E-lon,lat,alt_km'
  EPHEM_TYPE='OBSERVER', QUANTITIES='4'  apparent azimuth and elevation
  STEP_SIZE='1h'

Azimuth is measured from local north through east, elevation from the
local horizontal plane of the Moon's reference sphere (radius 1737.4 km).
LOLA heights are relative to the same sphere, so a site's altitude is
simply elevation_m / 1000.

Every response is cached on disk (data/cache/horizons/), so re-running the
pipeline never re-downloads, and results are reproducible offline.

Simplification: the observer's height uses the site's terrain height plus
the 2 m mast; Horizons' "apparent" values include light-time and aberration
but the Moon has no atmosphere, so there's no refraction to worry about.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "horizons"

SUN = "10"
EARTH = "399"
MOON = "301"


class HorizonsError(RuntimeError):
    """Horizons answered, but with an error message instead of data."""


def build_params(target, lon_e_deg, lat_deg, alt_km, start, stop, step="1h", center_body=MOON):
    """The exact query parameters for one observer-table request.

    Longitude is normalised to 0-360 east, which is what Horizons expects.
    start/stop are strings like '2027-01-01 00:00'.
    """
    lon_e = float(lon_e_deg) % 360.0
    return {
        "format": "json",
        "COMMAND": f"'{target}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": f"'coord@{center_body}'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{lon_e:.6f},{float(lat_deg):.6f},{float(alt_km):.5f}'",
        "START_TIME": f"'{start}'",
        "STOP_TIME": f"'{stop}'",
        "STEP_SIZE": f"'{step}'",
        "QUANTITIES": "'4'",
        "ANG_FORMAT": "'DEG'",
        "TIME_DIGITS": "'MINUTES'",
        "CSV_FORMAT": "'NO'",
    }


def _cache_path(params):
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]
    return CACHE_DIR / f"{key}.json"


def fetch(params, retries=4, timeout=120):
    """Run one Horizons query, using the disk cache when possible.

    Retries network failures with exponential backoff (2, 4, 8, 16 s).
    Raises HorizonsError if Horizons returns an error message.
    """
    path = _cache_path(params)
    if path.exists():
        payload = json.loads(path.read_text())
    else:
        last = None
        for attempt in range(retries + 1):
            try:
                resp = requests.get(API_URL, params=params, timeout=timeout)
                resp.raise_for_status()
                payload = resp.json()
                break
            except (requests.RequestException, ValueError) as exc:
                last = exc
                if attempt == retries:
                    raise
                time.sleep(2 ** (attempt + 1))
        else:  # pragma: no cover
            raise last
        if "error" in payload:
            raise HorizonsError(payload["error"])
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    if "error" in payload:
        raise HorizonsError(payload["error"])
    return payload["result"]


def parse_az_el(result_text):
    """Pull (time, azimuth, elevation) rows out of a Horizons text table.

    The data sits between the $$SOE and $$EOE markers. Each line looks like
        ' 2027-Feb-01 00:00 *   108.872458   0.049683'
    The symbols between the time and the numbers (like '*' for "Sun up at
    the observer" or 'm' for moonlight) vary, so we take the date and time
    from the start of the line and the last two numbers from the end.

    Returns (times as ISO strings ending in Z, az array, el array).
    """
    try:
        body = result_text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    except IndexError as exc:
        raise HorizonsError("No $$SOE/$$EOE data block in Horizons output") from exc
    times, az, el = [], [], []
    for line in body.strip().splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        t = datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%b-%d %H:%M").replace(tzinfo=timezone.utc)
        times.append(t.strftime("%Y-%m-%dT%H:%MZ"))
        az.append(float(parts[-2]))
        el.append(float(parts[-1]))
    if not times:
        raise HorizonsError("Horizons data block was empty")
    return times, np.array(az), np.array(el)


def az_el_series(target, lon_e_deg, lat_deg, alt_km, start, stop, step="1h", center_body=MOON):
    """Convenience wrapper: build the query, fetch (or load from cache), parse."""
    params = build_params(target, lon_e_deg, lat_deg, alt_km, start, stop, step, center_body)
    return parse_az_el(fetch(params))


def sun_earth_for_site(site, start, stop, step="1h", mast_m=2.0):
    """Sun and Earth azimuth/elevation every step for one site (a sites.json row).

    Observer height = site elevation + mast. Returns a dict of numpy arrays
    plus the shared list of ISO times. Raises if the two series don't line up.
    """
    alt_km = (float(site["elevation_m"]) + mast_m) / 1000.0
    t_sun, sun_az, sun_el = az_el_series(SUN, site["lon"], site["lat"], alt_km, start, stop, step)
    t_earth, earth_az, earth_el = az_el_series(EARTH, site["lon"], site["lat"], alt_km, start, stop, step)
    if t_sun != t_earth:
        raise HorizonsError("Sun and Earth time steps do not match")
    return {
        "times": t_sun,
        "sun_az_deg": sun_az,
        "sun_elev_deg": sun_el,
        "earth_az_deg": earth_az,
        "earth_elev_deg": earth_el,
    }
