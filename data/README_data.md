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

## Stage 6 / 10 / 14: shadow grids (`shared/grid_SITE.json`, all 9 sites)

```bash
python data/build_grid.py --year             # per-cell horizons + a year of sunlight, cached (about 1 min per site)
python planner/find_scenarios.py             # Harril's planner picks each site's 14-day window
python data/build_grid.py --from-scenarios   # write shared/grid_SITE.json for those windows
```

64 x 64 cells of **80 m** (a 5.1 km x 5.1 km operations area) centred on each site, 336 hourly steps (14 days),
aligned with the south-polar map (0 degrees longitude up). 3.8-5.1 MB per site, so the website should load only
the selected site's grid.

**How each cell's sunlight is computed** (`sunchaser_data/grid.py`):
- Near terrain (within 15 km): ray-cast from every cell on the LOLA 20 m DEM, 360 directions.
- Far terrain (15-150 km): rays cast on the LOLA 120 m DEM once per block of 8 x 8 cells; each cell computes
  its own angle to that terrain from its own ground height.
- The Sun's position comes from the site's timeline and is corrected per cell twice: for lunar curvature
  (a cell 1 km closer to the Sun sees it about 0.03 degrees higher) and for the turning of local north with
  longitude near the pole (the Sun's azimuth differs by a few degrees across 5 km).
- `sun_pct` = round(100 x visible fraction of the Sun's disk).

**Why 80 m cells and not 40 m.** The first grids were 2.56 km across (40 m cells). Tested on every site, the
reference rover's battery never fell below 48% on any crossing: no crossing takes longer than about 15 hours and
the rover survives about 22 hours of darkness, so no route could fail and the sun-chasing planner had nothing to
beat. We enlarged the area to 5.1 km, where traverses take 20-35 hours. The rover's specifications were not
changed.

**How each window was chosen** (handbook B.11, "pick a dramatic window with Harril"): the planner searched all of
2027 at each site for a departure and a start/target pair where the shortest route freezes and the sun-chasing
route survives and can then park safely at its target (`planner/find_scenarios.py`, results in
`planner/scenarios.json`). The grid window starts 24
hours before that departure.

| Site | Window start | Cell-hours lit | Lit, first day → last day | Cells steeper than 15° | Relief |
| --- | --- | --- | --- | --- | --- |
| Peak near Cabeus B | 2027-11-09 | 83% | 29% → 89% | 56% | 1776 m |
| Haworth | 2027-12-16 | 39% | 51% → 0% | 7% | 548 m |
| Malapert Massif | 2027-04-25 | 29% | 59% → 0% | 62% | 1056 m |
| Mons Mouton Plateau | 2027-01-16 | 58% | 62% → 0% | 3% | 443 m |
| Mons Mouton | 2027-01-01 | 36% | 58% → 11% | 31% | 969 m |
| Nobile Rim 1 | 2027-08-21 | 43% | 29% → 46% | 49% | 1395 m |
| Nobile Rim 2 | 2027-12-01 | 80% | 63% → 62% | 12% | 663 m |
| de Gerlache Rim 2 | 2027-12-07 | 53% | 43% → 68% | 51% | 837 m |
| Slater Plain | 2027-10-30 | 41% | 56% → 0% | 2% | 437 m |

The ridge sites (Malapert, de Gerlache Rim 2, Nobile Rim 1, Cabeus B) are well lit but steep: a real trade-off
between power and mobility.

**Limits:** azimuths every 1 degree; far terrain ray-cast per block of cells; 80 m cells average out smaller
features; the observer is the rover's 2 m mast; hourly steps.

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

## Stage 11: validation (`python data/validate.py`, results in `data/sites/validation.json`)

### Check 1: against NASA's published illumination maps

NASA's LOLA team publishes the average Sun and Earth visibility at the south pole over an 18.6-year lunar
nutation cycle (`AVGVISIB_75S_120M_201608` and `..._EARTH`, Mazarico et al. 2011, updated 2016,
https://pgda.gsfc.nasa.gov/products/69). Their quantity is the share of time **any part** of the Sun's (or
Earth's) disk is above the terrain. We computed the same quantity with our own pipeline (JPL Horizons + our LOLA
horizons) over 2027-2045 (one 18.6-year cycle, every 6 hours) at all 9 sites.

| Site | Sun: ours | Sun: NASA (3x3 pixel range) | Earth: ours | Earth: NASA |
| --- | --- | --- | --- | --- |
| Peak near Cabeus B | 52.9% | 52.4% (39.0-55.0%) | 79.6% | 72.5% |
| Haworth | 69.8% | 66.0% (47.7-67.7%) | 61.0% | 60.3% |
| Malapert Massif | 71.9% | 65.5% (38.8-78.8%) | 76.9% | 72.5% |
| Mons Mouton Plateau | 43.7% | 42.2% (40.5-43.0%) | 62.6% | 60.9% |
| Mons Mouton | 78.8% | 66.7% (37.3-78.4%) | 80.5% | 71.0% |
| Nobile Rim 1 | 84.5% | 76.3% (52.5-83.5%) | 70.2% | 65.6% |
| Nobile Rim 2 | 52.8% | 51.9% (29.3-52.4%) | 66.4% | 64.5% |
| de Gerlache Rim 2 | 78.9% | 74.6% (48.9-78.5%) | 61.8% | 60.0% |
| Slater Plain | 58.8% | 57.7% (50.1-59.1%) | 39.0% | 39.7% |

- **Correlation across sites: 0.978 (Sun), 0.987 (Earth).** Mean absolute difference 4.3 points (Sun),
  3.6 points (Earth).
- Ours is on average 4.3 points higher for the Sun. Two reasons, both checked:
  1. **Observer height.** With our 2 m mast we are +4.3 points; with the observer on the ground we are
     -9.6 points. NASA's map sits between the two: a couple of metres matter a lot when the Sun is this low.
  2. **Resolution and point choice.** NASA's pixel is 120 m; our points were chosen as the best-lit spot in
     20 m terrain. At 8 of 9 sites our value is within 2 points of NASA's 3x3-pixel range (it sits near the top
     of it, as you'd expect for the best spot).

### Check 2: against real landings

| Lander | Reported | Our model |
| --- | --- | --- |
| IM-1 Odysseus, 80.13 S 1.44 E, landed 2024-02-22 23:23 UTC (NASA/LROC) | Talked to Earth; "lost power and shut down with the start of the lunar night" on 29 Feb 2024 | Sun fully up and Earth in view at landing; Earth in view 100% of the mission; Sun still about 5 degrees up on 29 Feb; terrain sunset on 2 Mar 15:00 UTC |
| IM-2 Athena, 84.7906 S 29.1957 E, landed 2025-03-06 17:28 UTC (LROC) | Talked to Earth until 06:15 UTC on 7 Mar; came to rest on its side inside a shadowed 20 m crater | Sun fully up and Earth in view for the whole 13-hour operation on the surrounding terrain |

- Landing conditions match: both landers touched down in sunlight with Earth in view, as they needed to
  communicate.
- **IM-1 mismatch, reported honestly:** we predict terrain sunset 2.5 days after Odysseus shut down. Our model
  (LOLA 30 m near the site, ground height 2,594 m vs LROC's 2,579 m) sees the open terrain; Odysseus came to rest
  tilted on its side in a 1 km crater on a 12-degree slope, so its panels lost useful sunlight while the Sun was
  still about 5 degrees up. Our sunset is an upper bound on how long a lander there can run on solar power.
- **IM-2:** the 20 m crater Athena fell into is smaller than any LOLA pixel, so our model describes the terrain
  around it, not the crater floor.

Extra data for these checks (gitignored cache): `LDEM_75S_30M` (1.9 GB) for IM-1, and the two `AVGVISIB` maps
from `https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/`.

## Stage 13 (Insane): surface temperature (`surface_temp_k` in the timelines)

`sunchaser_data/thermal.py` is a 1D heat-conduction model of the top half-metre of regolith using the
published properties of **Hayne et al. 2017** (JGR Planets 122, 2371; fitted to LRO Diviner data), taken
exactly as coded in Hayne's open-source `heat1d` model: angle-dependent albedo, emissivity 0.95,
density and conductivity rising with depth (H = 0.07 m), temperature-dependent conductivity and heat
capacity, geothermal flow 0.018 W/m^2. Implicit 1-hour steps; the year is run three times and the last kept.

- **Sunlight on a tilted surface:** with the Sun about 1 degree up, slope matters enormously (a 10 degree slope
  facing the Sun sees it as if 11 degrees up). Each site's slope and facing direction come from the LOLA 20 m DEM
  (a plane over +/-40 m); the sites are gentle, 0.7-4.1 degrees, as landing sites must be.
- **Check against Diviner:** a synthetic equator day gives **385 K at noon and 92 K before dawn**, against
  Diviner's measured ~390 K and ~95 K (Williams et al. 2017; Hayne et al. 2017). Steady-state radiative balance
  is also tested.
- **At the sites (2027):** from about 44 K in the longest darkness to 134-208 K at most; Peak near Cabeus B
  reaches 208 K because its slope faces the Sun.

**Limits (context, not a substitute for Diviner):** no heating by sunlight scattered from, or infrared emitted by,
surrounding terrain, so shadowed hours read too cold (IM-2 reported about 100 K in its shadowed crater; our dark
hours bottom out at 44-63 K on open ground); one slope per site; Sun-Moon distance fixed at 1 AU (+/-3% flux).
