"""Stage 3: choose one landing point per Artemis III region and write shared/sites.json.

Run from the repo root:  python data/build_sites.py

For each of the 77 published candidate points (data/sites/artemis_candidate_points.csv):
  1. read its height from the LOLA 20 m DEM;
  2. ray-cast its terrain horizon: LOLA 20 m within 15 km, LOLA 120 m
     (reaching 75 deg S) from 15 to 150 km, with lunar curvature;
  3. get a year (2027) of hourly Sun and Earth positions from JPL Horizons;
  4. compute % of hours sunlit (at least half the Sun's disk visible),
     % with Earth in view, and the longest dark spell.
Then, per region, pick the point that is sunlit most often (ties broken by
hours with both Sun and Earth). Power is what keeps a rover alive.

Outputs:
  shared/sites.json                     one row per region (schema 2.1)
  data/sites/candidate_scores.csv       every candidate's numbers, for the
                                        Methods page and for checking our choice

Honest limits: the observer is a 2 m mast; terrain between DEM pixels is
interpolated; the horizon is sampled every 0.5 deg of azimuth.
"""

import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

from sunchaser_data import schema  # noqa: E402
from sunchaser_data.illumination import (  # noqa: E402
    horizon_for_point, light_series, load_standard_dems, summarise)

YEAR_START, YEAR_STOP = "2027-01-01 00:00", "2027-12-31 23:00"
CANDIDATES = ROOT / "data" / "sites" / "artemis_candidate_points.csv"
SCORES_OUT = ROOT / "data" / "sites" / "candidate_scores.csv"
SITES_OUT = ROOT / "shared" / "sites.json"
PAPER = "JGR Planets 2025, doi:10.1029/2025JE009434"


def load_candidates():
    lines = [ln for ln in CANDIDATES.read_text().splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def score_point(near, far, cand):
    lat, lon = float(cand["lat"]), float(cand["lon"])
    profile, coverage, elev = horizon_for_point(far, lat, lon, near_dem=near)
    site = {"lat": lat, "lon": lon, "elevation_m": elev}
    series = light_series(site, profile, YEAR_START, YEAR_STOP)
    return {**cand, "elevation_m": round(elev, 1), "horizon_coverage": round(coverage, 3),
            **{k: round(v, 1) for k, v in summarise(series).items()}}


def main():
    print("Loading LOLA DEMs (LDEM_80S_20M near, LDEM_75S_120M far)...")
    near, far = load_standard_dems()
    cands = load_candidates()
    print(f"Scoring {len(cands)} candidate points against a year of Horizons data...")
    with ThreadPoolExecutor(max_workers=3) as pool:  # be polite to JPL's servers
        scored = list(pool.map(lambda c: score_point(near, far, c), cands))

    fields = list(scored[0].keys())
    with SCORES_OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(scored)

    sites = []
    for region in dict.fromkeys(c["region"] for c in scored):  # keeps file order
        pts = [c for c in scored if c["region"] == region]
        best = max(pts, key=lambda c: (c["sunlit_pct"], c["both_pct"]))
        edge = "" if best["horizon_coverage"] >= 0.999 else (
            f" Some terrain beyond 80S is off the map ({100 * (1 - best['horizon_coverage']):.0f}% of directions).")
        sites.append({
            "id": region,
            "name": best["nasa_name"],
            "lat": float(best["lat"]),
            "lon": float(best["lon"]),
            "elevation_m": float(best["elevation_m"]),
            "source": f"NASA Artemis III candidate region (Oct 2024); point {best['point']} from {PAPER}; "
                      f"elevation from LRO LOLA LDEM_80S_20M",
            "notes": f"Sunlit {best['sunlit_pct']:.0f}% and Earth in view {best['earth_pct']:.0f}% of 2027 "
                     f"(LOLA terrain to 150 km); longest dark spell {best['longest_dark_h']:.0f} h.{edge}",
        })
        print(f"  {best['nasa_name']:22s} {best['point']:10s} sunlit {best['sunlit_pct']:5.1f}%  "
              f"earth {best['earth_pct']:5.1f}%  dark max {best['longest_dark_h']:5.0f} h  "
              f"(best of {len(pts)})")

    errors = schema.check_sites(sites)
    if errors:
        raise SystemExit("sites.json fails the schema:\n  " + "\n  ".join(errors))
    SITES_OUT.parent.mkdir(exist_ok=True)
    SITES_OUT.write_text(json.dumps(sites, indent=2) + "\n")
    print(f"Wrote {SITES_OUT.relative_to(ROOT)} ({len(sites)} sites, schema OK) and "
          f"{SCORES_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
