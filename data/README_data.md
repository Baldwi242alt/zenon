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

## Stage 5: timelines (`shared/timeline_SITE.json`)

```bash
python data/build_timelines.py    # about 1 minute (Horizons responses are cached)
```

One row per hour for all of 2027 (8,760 rows) for each of the 9 sites, about 2.1 MB per file.
Sun/Earth positions from JPL Horizons; horizons from the two-resolution LOLA ray casting (Stage 4);
`sun_frac` from the Sun-disk formula; `dsn_station` and `surface_temp_k` are `null` until Stages 9 and 13.

| Site | Sunlit | Earth in view | Both |
| --- | --- | --- | --- |
| Mons Mouton | 75.7% | 72.7% | 51.6% |
| Nobile Rim 1 | 80.6% | 62.1% | 47.9% |
| Malapert Massif | 68.3% | 71.4% | 44.5% |
| de Gerlache Rim 2 | 76.9% | 53.5% | 41.7% |
| Peak near Cabeus B | 52.3% | 68.9% | 35.6% |
| Haworth | 65.5% | 54.8% | 34.9% |
| Nobile Rim 2 | 50.9% | 60.9% | 30.5% |
| Mons Mouton Plateau | 40.9% | 56.6% | 25.5% |
| Slater Plain | 58.4% | 32.0% | 18.7% |

The per-site horizon profiles (720 directions) are saved in `data/sites/horizon_profiles.json` for the
shadow grid and for horizon plots on the Methods page. `data/tests/test_real_outputs.py` re-checks every
row: `sun_frac` agrees with the formula, `earth_visible` agrees with the elevations, and every hour of
2027 is present.

## Stage 6: shadow grid (`shared/grid_slater_plain.json`)

```bash
python data/build_grid.py --scan     # ~10 min first time (per-cell horizons cached in data/cache/grids/)
python data/build_grid.py --site slater_plain --start 2027-10-27T00:00Z
```

64 x 64 cells of 40 m (2.56 km square) centred on the Slater Plain point, 336 hourly steps (14 days),
aligned with the south-polar map (0 degrees longitude up). File size 4.7 MB.

**How each cell's sunlight is computed** (`sunchaser_data/grid.py`):
- Near terrain (within 15 km): ray-cast from every cell on the LOLA 20 m DEM, 360 directions.
- Far terrain (15-150 km): heights along each ray read once from the centre on the LOLA 120 m DEM;
  each cell computes its own angle to them from its own ground height.
- Sun position from the site's timeline; each cell's Sun elevation is corrected for lunar curvature
  (a cell 1 km closer to the Sun sees it about 0.03 degrees higher).
- `sun_pct` = round(100 x visible fraction of the Sun's disk).

**Why Slater Plain, 27 Oct - 10 Nov 2027:** `--scan` scored every daily 14-day window in 2027 at all 9 sites
for drama: shadows that move (cells lit 20-80% of the time), a mix of survivable and deadly cells
(longest dark spell above the 18 h placeholder limit), and plenty of light at the start. Slater Plain scored
highest (0.205) and is also the most drivable site: only 1% of cells are steeper than 15 degrees
(Malapert 21%, Nobile Rim 1 26%). Over the window the lit share falls day by day from 92% to 31% as the
Sun sinks, so the rover is racing the dark. The best window at every site is in
`data/sites/grid_window_options.csv` if Harril prefers another (Mons Mouton is the best near-side option
with good Earth contact and 5% steep cells).

**Limits:** azimuths every 1 degree; far terrain is ray-cast from the centre, not per cell; 40 m cells smooth
out smaller features; the rover's 2 m mast is the observer height. Near summits the horizon changes quickly
with height: at Malapert, a cell's averaged ground sits 0.5 m below the summit point, which raises nearby
horizon angles by about 0.13 degrees. That's real, not an error.

## Stage 7: scores and AI briefs (`shared/scores.json`)

```bash
python data/build_scores.py                       # template briefs (no API key needed)
ANTHROPIC_API_KEY=... python data/build_scores.py # AI briefs, checked by the numbers guard
```

1. For every month of 2027, every site and every landing time (every 6 h), score a 10-day mission
   (`scores.py`, using the usable-day rules from `metrics.py`).
2. **Month:** the one where the choice of site matters most (largest spread of best usable days
   between sites): **June 2027** (spread 3.3 days). Every month's spread is in `data/sites/scores_meta.json`;
   force another with `--month 2027-03`.
3. **Best landing per site, and ranking:** survives first, then usable days, then shorter longest dark spell,
   then more contact hours. *Team decision on top of handbook B.13, which ranks by usable days first:* a rover
   that freezes gets no more usable days, so a survivable landing beats one that looks better on paper.
   Example: in June, Nobile Rim 1's best landing has 7 usable days but an 84 h dark spell (limit 18 h),
   so it ranks last.

| Rank | Site | Usable days (of 10) | Longest dark | Best landing |
| --- | --- | --- | --- | --- |
| 1 | Peak near Cabeus B | 10 | 0 h | 19 Jun 18:00 |
| 2 | de Gerlache Rim 2 | 10 | 0 h | 22 Jun 06:00 |
| 3 | Haworth | 10 | 1 h | 21 Jun 06:00 |
| 4 | Mons Mouton | 8 | 9 h | 16 Jun 12:00 |
| 5 | Slater Plain | 6 | 0 h | 1 Jun 00:00 |
| 6 | Malapert Massif | 5 | 9 h | 13 Jun 18:00 |
| 7 | Nobile Rim 2 | 3 | 12 h | 8 Jun 06:00 |
| 8 | Mons Mouton Plateau | 0 | 6 h | 10 Jun 12:00 |
| 9 | Nobile Rim 1 | 7 (does not survive) | 84 h | 27 Jun 12:00 |

**Criteria:** `shared/criteria.json` isn't committed yet, so the PLACEHOLDER values from `CLAUDE.md` 2.7 are used
(10-day mission, 12 sun hours + 4 contact hours per usable day, 18 h dark limit). Rerun once Dhiran commits it.

**Briefs** (`briefs.py`): Claude (`claude-opus-5-5`, low effort, server-side refusal fallback on) writes three
sentences from the site's facts. The **numbers guard** extracts every number from the text and checks it
against the facts (allowing normal rounding and date parts); a brief with any invented number is retried
once, then replaced by the template. Without an API key every brief comes from the template, which is built
only from the facts. Which source each brief came from is recorded in `data/sites/scores_meta.json`
(currently: template for all 9). Tests use a fake client to check that an invented "99%" is rejected and that
a refusal falls back to the template.

## Stage 8: landing windows (`shared/windows_SITE.json`)

```bash
python data/build_windows.py     # a few seconds
```

Every landing time across 2027, every 6 hours (1,421 per site, until the last landing whose 10-day mission still
fits in the 2027 timeline), scored with the same rules as `scores.json`. About 200 KB per site. Feeds the
landing-window heatmap and the cost-of-a-slip chart (a 1/2/3/7-day slip is 4/8/12/28 rows later).

| Site | Landings the rover survives | Landings with all 10 days usable |
| --- | --- | --- |
| Nobile Rim 1 | 54.3% | 17.9% |
| Mons Mouton | 48.4% | 17.7% |
| de Gerlache Rim 2 | 45.3% | 12.2% |
| Malapert Massif | 37.3% | 14.4% |
| Haworth | 32.0% | 8.6% |
| Slater Plain | 28.9% | 0.3% |
| Peak near Cabeus B | 23.6% | 9.4% |
| Nobile Rim 2 | 23.3% | 7.2% |
| Mons Mouton Plateau | 13.6% | 6.0% |

With the placeholder 18 h dark limit, most of the year is not survivable at any site: the landing date matters
as much as the site. Slater Plain almost never has 10 usable days because Earth is in view only 32% of the time.

## Stage 9: Deep Space Network coverage (`dsn_station` in the timelines)

`sunchaser_data/dsn.py` asks JPL Horizons for the Moon's elevation every hour of 2027 from each DSN complex
(Goldstone, Madrid, Canberra; observer on Earth, target the Moon). A complex is available when the Moon is
more than 10 degrees above its horizon. In each timeline row, `dsn_station` is the available complex with the
Moon highest in its sky, but only when Earth is also visible from the lunar site; otherwise `null`.
`python data/build_timelines.py` rebuilds the timelines with it.

- At least one complex sees the Moon above 10 degrees for **98.1%** of 2027; the longest gap is **2 hours**.
  Canberra and Madrid each take 34.9% of hours, Goldstone 28.3%.
- So the binding limit on direct-to-Earth contact is the lunar terrain, not the DSN: requiring a DSN
  complex removes at most 0.9 percentage points of contact time at any site (Malapert: 71.4% Earth in view,
  70.5% with a DSN complex too).
- `earth_visible` (and so usable days, windows and scores) is unchanged; `dsn_station` adds which dish would
  carry the link, for the timeline tooltip and the copilot.

**Limits:** the Moon's centre is used (a south-pole site sits about 1,737 km from it, shifting elevations seen
from Earth by up to about 0.3 degrees); antenna scheduling and other missions are ignored.

## Stage 10: shadow grids for every site (`shared/grid_SITE.json`)

```bash
python data/build_grid.py --scan   # once: per-cell horizons for all sites + best windows (~10 min)
python data/build_grid.py --all    # writes every site's grid at its best window (seconds, uses the cache)
```

Same method as Stage 6, one 64 x 64 x 336 grid per site, each at the window the scan scored best for that site
(`data/sites/grid_window_options.csv`). 41 MB in total, 4.3-5.3 MB each, so the website should load only the
selected site's grid.

| Site | Window start | Cell-hours lit | Cells steeper than 15 degrees |
| --- | --- | --- | --- |
| Slater Plain (demo) | 2027-10-27 | 67% | 1% |
| Nobile Rim 2 | 2027-12-03 | 84% | 0% |
| Mons Mouton Plateau | 2027-10-06 | 77% | 3% |
| Mons Mouton | 2027-10-13 | 58% | 5% |
| Haworth | 2027-10-23 | 53% | 10% |
| Malapert Massif | 2027-10-19 | 61% | 21% |
| Nobile Rim 1 | 2027-11-15 | 54% | 26% |
| Peak near Cabeus B | 2027-01-22 | 91% | 30% |
| de Gerlache Rim 2 | 2027-10-21 | 53% | 35% |

The steep sites (Cabeus B, de Gerlache Rim 2, Nobile Rim 1) are ridges and peaks: good for sunlight, hard for
driving. That is a real trade-off worth showing in Rover Ops.
