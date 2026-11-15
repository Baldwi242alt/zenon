"""Stage 5: write shared/timeline_SITE.json for every site in shared/sites.json.

Run from the repo root:  python data/build_timelines.py

For each site, one row per hour for the whole of 2027 (8,760 rows):
  - Sun and Earth azimuth/elevation from JPL Horizons (cached);
  - the terrain horizon in the Sun's and Earth's directions, from the
    two-resolution LOLA horizon (Stage 4);
  - sun_frac: fraction of the Sun's disk above that horizon;
  - earth_visible: Earth's centre above the horizon in its direction.
  - dsn_station: the Deep Space Network complex with the Moon highest above
    its 10 deg mask (dsn.py), when Earth is also visible from the site;
    null when Earth is hidden or no complex can see the Moon.
  - surface_temp_k: regolith surface temperature from a 1D heat-conduction
    model with Hayne et al. 2017 properties, on the site's own slope
    (thermal.py). Context only; see that module for its limits.

Numbers are rounded to 2 decimals to keep each file around 1-2 MB.
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

from sunchaser_data import schema  # noqa: E402
from sunchaser_data.dsn import best_station, moon_elevations  # noqa: E402
from sunchaser_data import thermal  # noqa: E402
from sunchaser_data.illumination import (  # noqa: E402
    PROFILE_AZ, horizon_for_point, light_series, load_standard_dems, summarise)

YEAR_START, YEAR_STOP = "2027-01-01 00:00", "2027-12-31 23:00"
SHARED = ROOT / "shared"
PROFILES_OUT = ROOT / "data" / "sites" / "horizon_profiles.json"


def r2(x):
    return round(float(x), 2)


def build_timeline(site, profile, dsn, slope_aspect):
    s = light_series(site, profile, YEAR_START, YEAR_STOP)
    if dsn["times"] != s["times"]:
        raise SystemExit("DSN and site time steps do not line up")
    flux = thermal.absorbed_flux(s["sun_elev_deg"], s["sun_az_deg"], s["sun_frac"], *slope_aspect)
    temp = thermal.surface_temperature(flux)
    rows = []
    for i, t in enumerate(s["times"]):
        rows.append({
            "time": t,
            "sun_elev_deg": r2(s["sun_elev_deg"][i]),
            "sun_az_deg": r2(s["sun_az_deg"][i]) % 360,
            "sun_horizon_deg": r2(s["sun_horizon_deg"][i]),
            "sun_frac": r2(s["sun_frac"][i]),
            "earth_elev_deg": r2(s["earth_elev_deg"][i]),
            "earth_az_deg": r2(s["earth_az_deg"][i]) % 360,
            "earth_horizon_deg": r2(s["earth_horizon_deg"][i]),
            "earth_visible": bool(s["earth_visible"][i]),
            "dsn_station": dsn["station"][i] if s["earth_visible"][i] else None,
            "surface_temp_k": round(float(temp[i]), 1),
        })
    return {"site": site["id"], "start": s["times"][0], "step_h": 1, "rows": rows}, s


def main():
    sites = json.loads((SHARED / "sites.json").read_text())
    print("Loading LOLA DEMs...")
    near, far = load_standard_dems()
    times, els = moon_elevations(YEAR_START, YEAR_STOP)
    dsn = {"times": times, "station": best_station(els)}
    covered = sum(x is not None for x in dsn["station"]) / len(times)
    print(f"DSN: at least one complex sees the Moon above 10 deg for {100 * covered:.1f}% of hours")
    profiles = {}
    for site in sites:
        prof, coverage, ground = horizon_for_point(far, site["lat"], site["lon"], near_dem=near)
        profiles[site["id"]] = {"az_deg": PROFILE_AZ.tolist(), "horizon_deg": np.round(prof, 3).tolist(),
                                "coverage": coverage, "ground_m": round(ground, 1)}
        slope_aspect = thermal.site_slope_aspect(near, site["lat"], site["lon"])
        tl, series = build_timeline(site, prof, dsn, slope_aspect)
        temps = [r["surface_temp_k"] for r in tl["rows"]]
        errors = schema.check_timeline(tl)
        if errors:
            raise SystemExit(f"timeline_{site['id']} fails the schema:\n  " + "\n  ".join(errors[:10]))
        out = SHARED / f"timeline_{site['id']}.json"
        out.write_text(json.dumps(tl, separators=(",", ":")))
        m = summarise(series)
        link = sum(r["dsn_station"] is not None for r in tl["rows"]) / len(tl["rows"])
        print(f"  {out.name:36s} {len(tl['rows'])} rows  {out.stat().st_size / 1e6:4.2f} MB  "
              f"sunlit {m['sunlit_pct']:5.1f}%  earth {m['earth_pct']:5.1f}%  "
              f"earth+DSN {100 * link:5.1f}%  both {m['both_pct']:5.1f}%  slope {slope_aspect[0]:4.1f} deg "
              f"facing {slope_aspect[1]:3.0f} deg  T {min(temps):5.1f}-{max(temps):5.1f} K")
    # Saved for the shadow grid (Stage 6) and the Methods page (horizon plots).
    PROFILES_OUT.write_text(json.dumps(profiles, separators=(",", ":")))
    print(f"Wrote {len(sites)} timelines (schema OK) and {PROFILES_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
