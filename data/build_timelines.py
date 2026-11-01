"""Stage 5: write shared/timeline_SITE.json for every site in shared/sites.json.

Run from the repo root:  python data/build_timelines.py

For each site, one row per hour for the whole of 2027 (8,760 rows):
  - Sun and Earth azimuth/elevation from JPL Horizons (cached);
  - the terrain horizon in the Sun's and Earth's directions, from the
    two-resolution LOLA horizon (Stage 4);
  - sun_frac: fraction of the Sun's disk above that horizon;
  - earth_visible: Earth's centre above the horizon in its direction.
dsn_station (Pro) and surface_temp_k (Insane) are null until those stages.

Numbers are rounded to 2 decimals to keep each file around 1-2 MB.
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

from sunchaser_data import schema  # noqa: E402
from sunchaser_data.illumination import (  # noqa: E402
    PROFILE_AZ, horizon_for_point, light_series, load_standard_dems, summarise)

YEAR_START, YEAR_STOP = "2027-01-01 00:00", "2027-12-31 23:00"
SHARED = ROOT / "shared"
PROFILES_OUT = ROOT / "data" / "sites" / "horizon_profiles.json"


def r2(x):
    return round(float(x), 2)


def build_timeline(site, profile):
    s = light_series(site, profile, YEAR_START, YEAR_STOP)
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
            "dsn_station": None,
            "surface_temp_k": None,
        })
    return {"site": site["id"], "start": s["times"][0], "step_h": 1, "rows": rows}, s


def main():
    sites = json.loads((SHARED / "sites.json").read_text())
    print("Loading LOLA DEMs...")
    near, far = load_standard_dems()
    profiles = {}
    for site in sites:
        prof, coverage, ground = horizon_for_point(far, site["lat"], site["lon"], near_dem=near)
        profiles[site["id"]] = {"az_deg": PROFILE_AZ.tolist(), "horizon_deg": np.round(prof, 3).tolist(),
                                "coverage": coverage, "ground_m": round(ground, 1)}
        tl, series = build_timeline(site, prof)
        errors = schema.check_timeline(tl)
        if errors:
            raise SystemExit(f"timeline_{site['id']} fails the schema:\n  " + "\n  ".join(errors[:10]))
        out = SHARED / f"timeline_{site['id']}.json"
        out.write_text(json.dumps(tl, separators=(",", ":")))
        m = summarise(series)
        print(f"  {out.name:36s} {len(tl['rows'])} rows  {out.stat().st_size / 1e6:4.2f} MB  "
              f"sunlit {m['sunlit_pct']:5.1f}%  earth {m['earth_pct']:5.1f}%  both {m['both_pct']:5.1f}%")
    # Saved for the shadow grid (Stage 6) and the Methods page (horizon plots).
    PROFILES_OUT.write_text(json.dumps(profiles, separators=(",", ":")))
    print(f"Wrote {len(sites)} timelines (schema OK) and {PROFILES_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
