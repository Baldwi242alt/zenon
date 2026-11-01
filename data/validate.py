"""Stage 11: validate Sunchaser's lighting and Earth visibility against independent evidence.

Run from the repo root:  python data/validate.py

Check 1: NASA's published illumination maps
  The LOLA team (Mazarico et al. 2011, updated 2016) published maps of the
  average Sun and Earth visibility at the south pole over an 18.6-year lunar
  nutation cycle: AVGVISIB_75S_120M_201608(.IMG and _EARTH.IMG), from
  https://pgda.gsfc.nasa.gov/products/69. Their definition: the fraction of
  timesteps when ANY part of the Sun's (or Earth's) disk is above the terrain.
  We compute the same quantity with our own pipeline (JPL Horizons + our
  LOLA horizons) over an 18.6-year span (2027-2045, every 6 hours) at all 9
  sites, and compare.

Check 2: real landings
  IM-1 (Odysseus): landed 2024-02-22 23:23 UTC at 80.13 S, 1.44 E
    (NASA/LROC); "On February 29, Odysseus lost power and shut down with the
    start of the lunar night" (Wikipedia, IM-1). Our model should show the
    Sun up at landing, Earth in view, and sunset around 29 February.
  IM-2 (Athena): landed 2025-03-06 17:28:50 UTC at 84.7906 S, 29.1957 E
    (LROC), last contact 2025-03-07 06:15 UTC. It came to rest on its side
    inside a 20 m crater in shadow, which no LOLA map can resolve, so our
    model describes the open terrain around it.

Outputs: data/sites/validation.json and a printed report.
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

from sunchaser_data.constants import SUN_ANGULAR_RADIUS_DEG  # noqa: E402
from sunchaser_data.dem import PolarDEM  # noqa: E402
from sunchaser_data.horizon import interp_horizon  # noqa: E402
from sunchaser_data.horizons import EARTH, SUN, az_el_series  # noqa: E402
from sunchaser_data.illumination import PROFILE_AZ, horizon_for_point, load_standard_dems  # noqa: E402
from sunchaser_data.sunfrac import sun_visible_fraction  # noqa: E402

ILLUM = ROOT / "data" / "cache" / "illum"
OUT = ROOT / "data" / "sites" / "validation.json"
SPAN = ("2027-01-01 00:00", "2045-08-08 00:00", "6h")   # one 18.6-year nutation cycle
EARTH_ANGULAR_RADIUS_DEG = 0.95   # Earth (6,371 km) seen from 384,400 km: atan(6371/384400) = 0.95 deg
MAST_M = 2.0

LANDINGS = [
    {"id": "im1", "name": "IM-1 Odysseus", "lat": -80.13, "lon": 1.44,
     "landed": "2024-02-22 23:00", "until": "2024-03-03 00:00",
     "event": "shut down at the start of the lunar night on 29 Feb 2024"},
    {"id": "im2", "name": "IM-2 Athena", "lat": -84.7906, "lon": 29.1957,
     "landed": "2025-03-06 17:00", "until": "2025-03-07 07:00",
     "event": "landed 17:28 UTC on 6 Mar, last contact 06:15 UTC on 7 Mar 2025"},
]


def nasa_value(dem, lat, lon):
    """Bilinear value of a NASA map at a point, plus the 3x3-pixel range around it."""
    v = dem.height_at(lat, lon)
    r, c = (int(round(float(x))) for x in dem.latlon_to_rc(lat, lon))
    block = dem.heights[r - 1:r + 2, c - 1:c + 2]
    return v, float(block.min()), float(block.max())


def visibility(lat, lon, profile, elev_m, span, mast_m=MAST_M):
    """Our versions of NASA's two quantities over a time span."""
    alt = (elev_m + mast_m) / 1000.0
    _, s_az, s_el = az_el_series(SUN, lon, lat, alt, *span)
    _, e_az, e_el = az_el_series(EARTH, lon, lat, alt, *span)
    s_hz = interp_horizon(profile, PROFILE_AZ, s_az)
    e_hz = interp_horizon(profile, PROFILE_AZ, e_az)
    return {
        "sun_any": float(np.mean(s_el + SUN_ANGULAR_RADIUS_DEG > s_hz)),       # NASA's definition
        "sun_mean_frac": float(np.mean(sun_visible_fraction(s_el, s_hz))),
        "earth_any": float(np.mean(e_el + EARTH_ANGULAR_RADIUS_DEG > e_hz)),  # NASA's definition
        "earth_centre": float(np.mean(e_el > e_hz)),                          # what our timelines use
    }


def check_maps(near, far):
    sun_map = PolarDEM(ILLUM / "AVGVISIB_75S_120M_201608.IMG")
    earth_map = PolarDEM(ILLUM / "AVGVISIB_75S_120M_201608_EARTH.IMG")
    sites = json.loads((ROOT / "shared" / "sites.json").read_text())
    rows = []
    print("Check 1: NASA average visibility maps (18.6-year averages)")
    print(f"  {'site':22s} {'Sun: ours':>9s} {'NASA':>6s} {'(3x3)':>13s}   {'Earth: ours':>11s} {'NASA':>6s}")
    for s in sites:
        prof, _, ground = horizon_for_point(far, s["lat"], s["lon"], near_dem=near)
        ours = visibility(s["lat"], s["lon"], prof, ground, SPAN)
        # Same point with the observer on the ground (no mast), to see how much the 2 m mast adds.
        prof0, _, _ = horizon_for_point(far, s["lat"], s["lon"], near_dem=near, mast_m=0.0)
        ours["sun_any_no_mast"] = visibility(s["lat"], s["lon"], prof0, ground, SPAN, mast_m=0.0)["sun_any"]
        ns, ns_lo, ns_hi = nasa_value(sun_map, s["lat"], s["lon"])
        ne, _, _ = nasa_value(earth_map, s["lat"], s["lon"])
        rows.append({"site": s["id"], "name": s["name"], **{k: round(v, 3) for k, v in ours.items()},
                     "nasa_sun": round(ns, 3), "nasa_sun_3x3": [round(ns_lo, 3), round(ns_hi, 3)],
                     "nasa_earth": round(ne, 3)})
        print(f"  {s['name']:22s} {100 * ours['sun_any']:8.1f}% {100 * ns:5.1f}% "
              f"({100 * ns_lo:4.1f}-{100 * ns_hi:4.1f}%)   {100 * ours['earth_any']:10.1f}% {100 * ne:5.1f}%")
    ds = np.array([r["sun_any"] - r["nasa_sun"] for r in rows]) * 100
    de = np.array([r["earth_any"] - r["nasa_earth"] for r in rows]) * 100
    summary = {
        "sun_mean_diff_pts": round(float(ds.mean()), 1), "sun_mean_abs_diff_pts": round(float(np.abs(ds).mean()), 1),
        "sun_max_abs_diff_pts": round(float(np.abs(ds).max()), 1),
        "sun_mean_diff_no_mast_pts": round(float(np.mean([r["sun_any_no_mast"] - r["nasa_sun"] for r in rows]) * 100), 1),
        "sun_within_3x3_pts": sum(r["nasa_sun_3x3"][0] - 0.02 <= r["sun_any"] <= r["nasa_sun_3x3"][1] + 0.02
                                  for r in rows),
        "sun_correlation": round(float(np.corrcoef([r["sun_any"] for r in rows], [r["nasa_sun"] for r in rows])[0, 1]), 3),
        "earth_mean_diff_pts": round(float(de.mean()), 1), "earth_mean_abs_diff_pts": round(float(np.abs(de).mean()), 1),
        "earth_max_abs_diff_pts": round(float(np.abs(de).max()), 1),
        "earth_correlation": round(float(np.corrcoef([r["earth_any"] for r in rows], [r["nasa_earth"] for r in rows])[0, 1]), 3),
    }
    print(f"  Sun:   ours - NASA = {summary['sun_mean_diff_pts']:+.1f} points on average, "
          f"mean |diff| {summary['sun_mean_abs_diff_pts']:.1f}, max {summary['sun_max_abs_diff_pts']:.1f}, "
          f"correlation {summary['sun_correlation']:.3f}")
    print(f"  Without the 2 m mast: ours - NASA = {summary['sun_mean_diff_no_mast_pts']:+.1f} points; "
          f"ours within 2 points of NASA's 3x3-pixel range at {summary['sun_within_3x3_pts']}/{len(rows)} sites")
    print(f"  Earth: ours - NASA = {summary['earth_mean_diff_pts']:+.1f} points on average, "
          f"mean |diff| {summary['earth_mean_abs_diff_pts']:.1f}, max {summary['earth_max_abs_diff_pts']:.1f}, "
          f"correlation {summary['earth_correlation']:.3f}")
    return rows, summary


def check_landings(near, far):
    print("Check 2: real landings")
    # IM-1 is at 80.1 S, just outside the 20 m DEM (which stops at 80 S); LOLA's 30 m DEM
    # reaching 75 S covers it and resolves the 1 km crater it landed in.
    near_75 = PolarDEM.from_cache("LDEM_75S_30M", lazy=True)
    results = []
    for L in LANDINGS:
        use_near = near if L["lat"] < -80.5 else near_75
        prof, coverage, ground = horizon_for_point(far, L["lat"], L["lon"], near_dem=use_near)
        alt = (ground + MAST_M) / 1000.0
        t, s_az, s_el = az_el_series(SUN, L["lon"], L["lat"], alt, L["landed"], L["until"], "1h")
        _, e_az, e_el = az_el_series(EARTH, L["lon"], L["lat"], alt, L["landed"], L["until"], "1h")
        frac = sun_visible_fraction(s_el, interp_horizon(prof, PROFILE_AZ, s_az))
        earth = e_el > interp_horizon(prof, PROFILE_AZ, e_az)
        lit = frac >= 0.5
        sunset = next((t[i] for i in range(1, len(t)) if lit[i - 1] and not lit[i]), None)
        res = {"id": L["id"], "name": L["name"], "lat": L["lat"], "lon": L["lon"],
               "dem": f"{use_near.name} (near) + {far.name} (far)",
               "ground_m": round(ground, 1), "reported": L["event"],
               "at_landing": {"time": t[0], "sun_frac": round(float(frac[0]), 2), "earth_visible": bool(earth[0])},
               "sunlit_hours_pct": round(100 * float(lit.mean()), 1),
               "earth_visible_pct": round(100 * float(earth.mean()), 1),
               "first_sunset": sunset,
               "hourly": [{"time": t[i], "sun_frac": round(float(frac[i]), 2), "earth_visible": bool(earth[i])}
                          for i in range(len(t))]}
        results.append(res)
        print(f"  {L['name']}: model ground {ground:.0f} m; at landing ({t[0]}) sun_frac {frac[0]:.2f}, "
              f"Earth {'visible' if earth[0] else 'hidden'}; sunlit {res['sunlit_hours_pct']}% and Earth visible "
              f"{res['earth_visible_pct']}% of hours until {L['until'][:10]}; first sunset {sunset}. "
              f"Reported: {L['event']}.")
    return results


def main():
    near, far = load_standard_dems()
    rows, summary = check_maps(near, far)
    landings = check_landings(near, far)
    OUT.write_text(json.dumps({"maps": {"source": "NASA LOLA AVGVISIB_75S_120M_201608 (Mazarico et al. 2011, "
                                                  "updated 2016), pgda.gsfc.nasa.gov/products/69",
                                        "span": SPAN, "sites": rows, "summary": summary},
                               "landings": landings}, indent=1) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
