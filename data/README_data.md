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
| `dem.py` | LOLA elevation loading | Stage 4 (needs network access) |

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
