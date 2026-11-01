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
| `illumination.py` | Terrain horizon to 150 km + hourly Sun/Earth visibility at a point | Done (80 m DEM) |

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
- **Choice:** for each point, terrain horizon from the LOLA 80 m DEM out to 150 km, plus a year (2027) of
  hourly Sun and Earth positions from JPL Horizons (each point queried separately, because points 40 km
  apart see the Sun up to 1.4 degrees differently). Per region we keep the point sunlit most often.
  Every candidate's numbers are in `data/sites/candidate_scores.csv`.
- **DEM orientation check:** 0 degrees longitude points up the LOLA image; confirmed by sampling Mons Mouton
  (+6.4 km), Malapert (+4.7 km) and Shackleton's floor (-2.8 km).

| Region | Point | Sunlit (2027) | Earth in view | Longest dark spell | Range across the region's points |
| --- | --- | --- | --- | --- | --- |
| Nobile Rim 1 | NR103 | 81.3% | 62.1% | 271 h | 46.6-81.3% |
| de Gerlache Rim 2 | dGR2_K2023 | 76.9% | 53.5% | 250 h | 20.7-76.9% |
| Mons Mouton | MMO02 | 74.6% | 71.7% | 387 h | 27.0-74.6% |
| Malapert Massif | MMA03 | 66.1% | 69.4% | 489 h | 16.7-66.1% |
| Haworth | HW_K2023 | 65.4% | 54.8% | 409 h | 17.4-65.4% |
| Slater Plain | SP09 | 59.2% | 33.1% | 370 h | 17.9-59.2% |
| Peak near Cabeus B | PCB04 | 52.8% | 69.6% | 366 h | 35.5-52.8% |
| Nobile Rim 2 | NR205 | 51.1% | 60.9% | 405 h | 28.5-51.1% |
| Mons Mouton Plateau | MMP11 | 40.6% | 56.5% | 500 h | 10.7-40.6% |

Sanity: near-side regions (longitude near 0, such as Malapert and Mons Mouton) see Earth far more than the
far-side Slater Plain (33%), as expected. "Longest dark spell" is the worst case across the whole year,
including the season when the Sun sits lowest.

**Limits:** 80 m terrain everywhere for now (Stage 4 adds a sharper DEM nearby); the observer is a 2 m mast;
Peak near Cabeus B, Nobile Rim 2 and Mons Mouton Plateau are near the DEM's 80 degree S edge, so 10-21% of their
directions lose terrain more than about 100 km away. These numbers are checked against NASA's published
illumination maps in Stage 11.
