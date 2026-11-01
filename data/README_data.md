# Data pipeline (owner: Baldwin)

Produces the shared files in `shared/`: `sites.json`, `timeline_SITE.json`,
`grid_SITE.json`, `windows_SITE.json`, `scores.json` (schemas in `CLAUDE.md` Section 2).

## Setup

```bash
pip install -r data/requirements.txt
python -m pytest data/tests
```

## Fake data (for teammates, available now)

`data/fake/` holds **FAKE** files in exactly the shared schemas, so the website
and planner can be built before real NASA data exists. Regenerate with:

```bash
python data/fake/make_fake.py
```

The Sun/Earth motion and terrain in these files are invented. The shadow
ray casting, Sun-disk fraction and scoring code are the real pipeline code.

| File | Contents |
| --- | --- |
| `sites.json` | 3 fake sites (A mostly lit, B borderline, C poor) |
| `timeline_site_{a,b,c}.json` | One week of hourly rows from 2027-02-01 |
| `grid_site_a.json` | 64 x 64 cells, 40 m, 336 hourly steps, ray-cast shadows |
| `scores.json` | Ranked fake scores using the placeholder criteria |

## Modules

| Module | What it does | Status |
| --- | --- | --- |
| `constants.py` | Moon radius, Sun angular radius, mast height | Done |
| `sunfrac.py` | Visible fraction of the Sun's disk above the horizon | Done, tested |
| `horizon.py` | Terrain horizon by ray casting with lunar curvature | Done, tested on synthetic terrain |
| `metrics.py` | Usable days, sun/contact hours, longest dark spell | Done, tested |
| `schema.py` | Checks every shared file against the data contract | Done |
| `horizons.py` | JPL Horizons client with disk cache and retries | Done, tested (offline fixture + live) |
| `dem.py` | LOLA polar DEM loading, stereographic projection, local north/east | Done, tested |
| `illumination.py` | Two-resolution terrain horizon to 150 km + hourly Sun/Earth visibility | Done, tested |

## Limits (stated honestly)

- Sun-disk fraction treats the horizon as flat across the 0.53 degree disk and ignores limb darkening.
- `horizon_profile` only sees terrain inside the DEM it is given; real sites need a DEM reaching about 150 km.
- `metrics.py` uses placeholder criteria until Dhiran commits `shared/criteria.json`.

## Stage 2 check: real Horizons data

```bash
python data/check_horizons.py            # default point -89.45, 137.3 E
python data/check_horizons.py -88.0 300 1000
```

Result for -89.45, 137.3 E over 2027 (8,760 hours): Sun elevation stays within
±2.09° (1.54° axis tilt + 0.55° distance from the pole), the Sun's azimuth turns
once every 29.53 days (the lunar day), and Earth's elevation swings ±6.8°
(libration). All match the expected south-pole physics. Note: Horizons' Earth
rotation data is a prediction after January 2027; this affects times by well
under a second, which is negligible here.

Live network tests run with `SUNCHASER_LIVE=1 python -m pytest data/tests`.

## Stage 3: sites (`shared/sites.json`)

```bash
# one-time download (115 MB) into the gitignored cache
mkdir -p data/cache/lola
curl -o data/cache/lola/LDEM_80S_80M.IMG https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/LDEM_80S_80M.IMG
curl -o data/cache/lola/LDEM_80S_80M.LBL https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/LDEM_80S_80M.LBL
python data/build_sites.py     # about 2 minutes
```

- **Regions:** NASA's nine Artemis III candidate regions (October 2024 update).
- **Candidate points:** the 77 published landing points inside those regions, from Appendix A of
  "Assessing Potential Landing Sites With Favorable Illumination and Accessible, Potentially
  Volatile-Rich Permanently Shadowed Regions Within Artemis Candidate Landing Regions",
  JGR Planets (2025), doi:10.1029/2025JE009434 (`data/sites/artemis_candidate_points.csv`).
- **Choice:** for each point, terrain horizon from LOLA (two resolutions, see Stage 4) out to 150 km, plus a year (2027) of
  hourly Sun and Earth positions from JPL Horizons (each point queried separately, because points 40 km
  apart see the Sun up to 1.4 degrees differently). Per region we keep the point sunlit most often.
  Every candidate's numbers are in `data/sites/candidate_scores.csv`.
- **DEM orientation check:** 0 degrees longitude points up the LOLA image; confirmed by sampling Mons Mouton
  (+6.4 km), Malapert (+4.7 km) and Shackleton's floor (-2.8 km).

| Region | Point | Sunlit (2027) | Earth in view | Longest dark spell | Range across the region's points |
| --- | --- | --- | --- | --- | --- |
| Nobile Rim 1 | NR103 | 80.6% | 62.1% | 224 h | see `candidate_scores.csv` |
| de Gerlache Rim 2 | dGR2_K2023 | 76.9% | 53.5% | 250 h | |
| Mons Mouton | MMO02 | 75.7% | 72.7% | 390 h | |
| Malapert Massif | MMA03 | 68.3% | 71.4% | 479 h | |
| Haworth | HW_K2023 | 65.5% | 54.8% | 403 h | |
| Slater Plain | SP09 | 58.4% | 32.0% | 380 h | |
| Peak near Cabeus B | PCB04 | 52.3% | 68.9% | 370 h | |
| Nobile Rim 2 | NR205 | 50.9% | 60.9% | 405 h | |
| Mons Mouton Plateau | MMP11 | 40.9% | 56.6% | 497 h | |

Sanity: near-side regions (longitude near 0, such as Malapert and Mons Mouton) see Earth far more than the
far-side Slater Plain (33%), as expected. "Longest dark spell" is the worst case across the whole year,
including the season when the Sun sits lowest.

**Limits:** the observer is a 2 m mast; terrain between pixels is interpolated; the horizon is sampled every
0.5 degrees of azimuth. These numbers are checked against NASA's published illumination maps in Stage 11.

## Stage 4: terrain horizons (two resolutions)

```bash
# one-time downloads into the gitignored cache (about 2 GB in total)
for f in LDEM_80S_20M LDEM_75S_120M; do
  curl -o data/cache/lola/$f.IMG https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/$f.IMG
  curl -o data/cache/lola/$f.LBL https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/$f.LBL
done
```

| Distance from the observer | DEM | Why |
| --- | --- | --- |
| 0 to 15 km | LOLA `LDEM_80S_20M` (20 m pixels, sampled every 20 m) | Small nearby bumps can hide a Sun that is only 1 degree up |
| 15 to 150 km | LOLA `LDEM_75S_120M` (120 m pixels, reaches 75 degrees S) | Only big mountains matter far away, but the map must reach far enough |

The horizon in each direction is the higher of the two, both computed from the same observer height
(20 m DEM + 2 m mast) and including lunar curvature. The 20 m DEM is 1.8 GB, so only a 30 km square
around each point is read from disk.

**What changed against the 80 m-only run (all 77 points):** sunlit time fell by 0.5 percentage points on
average (largest change 4.2 points, at HW02) because small nearby bumps now show up; every point now has
terrain in all directions to 150 km (previously 10-21% of directions were cut off for three regions); the
20 m and 80 m DEMs agree on point heights to within 1.6 m. The chosen point in each region did not change.

Test: `data/tests/test_two_res.py` builds two tiny fake DEM files with a nearby plateau and a distant
plateau and checks both horizon angles against hand-worked values.
