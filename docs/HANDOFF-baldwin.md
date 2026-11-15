# Sunchaser: Baldwin's Full Handoff

**Team Zenon · NASA Space Apps Challenge 2026 · November 14–15, 2026**
**Owner:** Baldwin (data, AI and tech lead) · **Branch:** `data-(Baldwin)` · **Writes in:** `data/`, `api/`, `CLAUDE.md`, and shared files `sites.json`, `timeline_*.json`, `grid_*.json`, `windows_*.json`, `scores.json`

> **For Claude Code:** this file is the complete transfer of a planning conversation held on November 1, 2026 (Singapore time). Read it together with `CLAUDE.md` (project brief and data contract, which is authoritative for schemas). Part A is the history and decisions, Part B is Baldwin's build guide, Part C is reference material. Baldwin is the strongest coder on the team and carries the heaviest load.

---

# Part A: What happened and what was decided

## A.1 Timeline of the conversation

1. **Brief:** Baldwin and two friends (Harril and Dhiran) are entering NASA Space Apps 2026. He asked for solution ideas for every 2026 challenge and the single most impressive one for a portfolio.
2. **Research:** the official site (spaceappschallenge.org) blocks automated reading, so challenge statements and objectives were gathered from local-event pages (Lucerne, Valencia, UAE) and the Space Data Atlas (spacedata.swapniltamse.com), which was refreshed against the full statements on Oct 29, 2026.
3. **All 14 challenges** were analysed with a solution for each (Part C.1) in a Claude Docs document called **"Space Apps 2026: Challenge Playbook"** (https://claude.ai/artifact/P8B7rscxUsqzQTKPv14ehM, private to Baldwin).
4. **First pick: Planet X and SPHEREx** (moving-object detection in SPHEREx images). Rejected because the team doesn't know computer vision.
5. **Flame in Freefall** was suggested as the easier AI option. Baldwin then asked for something mixing **robotics, AI, engineering and business** that is understandable yet shocking to employers.
6. **Final pick: Lunar Landing Site Navigator** (renamed from "CLPS Lunar Mission Browser"; the old URL is dead). Product name: **Sunchaser**.
7. Reasons: covers all four areas naturally (CLPS is NASA buying commercial Moon deliveries; landers and rovers; power/comms engineering; AI planning); one-sentence explainable; strong visual demo; no computer vision; all data free with no login.
8. **Honest risks raised:** at least eight polished public repos already exist for this challenge (mostly site/date comparison only: none seen with a rover survival sim, sun-chasing routes or a business case, which is Sunchaser's edge); judges score against the brief so the site/date browser must be excellent; the route planner is the hardest piece.
9. **Team roles set:** Baldwin (coding, AI, analytics) → data/AI/tech lead; Harril (robotics) → rover and planner; Dhiran (engineering + business) → specs, business, website, pitch.
10. **GitHub:** repo `sunchaser`, branches created by Baldwin in GitHub Desktop: `main`, `data-(Baldwin)`, `planner-(Harril)`, `web-(Dhiran)`. (First attempt failed because the repo was empty; fixed by committing a README to `main` first.) Each teammate clones the whole repo and works only on their branch. Pull requests into `main` at checkpoints; merge order data → planner → web; then everyone does **Branch → Update from main**.
11. **Team page text** and a project description were written (Part C.3).
12. **Handbooks:** standalone, very detailed files were written for Harril (`plan-robotics.md`) and Dhiran (`plan-engineering-business.md`), each opening with a brief for their AI and tiered Core → Pro → Insane. The project scope was raised to "insane" level at Baldwin's request.
13. **Issues so far:** Harril's AI thought it had to wait for Baldwin's data (it doesn't: the handbook makes him generate a fake world in the same schema). Harril pushed code but Baldwin saw an empty file (likely causes: viewing `main` instead of `planner-(Harril)`, unsaved VS Code file, VS Code opened on a different folder, or committed but not pushed).
14. **Transfer:** Baldwin is moving to Claude Code; this file and `CLAUDE.md` are the result.

## A.2 Key decisions (don't relitigate without reason)

| Decision | Choice |
| --- | --- |
| Challenge | Lunar Landing Site Navigator: https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/ |
| Product | Sunchaser: where to land, when, how to drive so the rover never freezes, and what it's worth |
| Team name | Zenon |
| Tiers | Core → Pro → Insane (see `CLAUDE.md` 1.5) |
| Data sharing | All JSON in `shared/`, one owner per file, schemas in `CLAUDE.md` Section 2 |
| Parallel work | Everyone builds on fake files in the agreed schema until real data lands |
| Website | React + TypeScript + Vite, `publicDir: '../shared'`, deployed on Vercel from repo root |
| AI | Precomputed briefs (Core); copilot serverless function with tool calling (Pro); numbers only from computed data |
| Planner | Space-time A* with energy constraint and dominance pruning; Monte Carlo survival probability |

## A.3 Rules and caveats raised

- **Build during the event.** Several teams state Space Apps rules require project code to be written during Nov 14–15. Baldwin should **check the official rules page**. Prep (learning, research, notebooks in throwaway files, planning documents) is fine before. Note: Harril has apparently started coding already; flag the rule to the team.
- **AI use:** check the rules for AI guidance and disclose AI use in the README regardless.
- **No project guarantees a job.** What helps: live demo link, one headline number, clear README, 60-second video, every member able to explain the system.
- **Official resource lists** open on the Space Apps site on **Nov 13**; Space Data Atlas suggestions were curated by a third party.

## A.4 Status as of Nov 1, 2026 (evening)

| Item | Status |
| --- | --- |
| Challenge chosen | Done |
| Roles | Done |
| GitHub repo + branches | Done |
| Harril's handbook | Done (`plan-robotics.md`) |
| Dhiran's handbook | Done (`plan-engineering-business.md`) |
| `CLAUDE.md` / `PROJECT.md` | Done (commit to repo root on `main` or `data-(Baldwin)`) |
| Baldwin's build guide | Done (Part B below) |
| Claude Doc "Challenge Playbook" | Has the older, simpler Sunchaser plan; superseded by these files |
| Space Apps registration and team formation on the site | Check: not confirmed in chat |
| Rules check (build window, AI) | Open |
| Harril's empty-push issue | Open |

---

# Part B: Baldwin's build guide

## B.1 Your mission

You produce the **truth** of Sunchaser: the lighting and communication data everything else stands on, the landing-window scan, the site scores, and the AI. You also run the repo: `CLAUDE.md`, checkpoint merges, unblocking teammates.

**You read:** `shared/criteria.json` and `shared/rover.json` (Dhiran).
**You write:** `shared/sites.json`, `shared/timeline_SITE.json`, `shared/grid_SITE.json`, `shared/windows_SITE.json`, `shared/scores.json` (schemas 2.1–2.5 in `CLAUDE.md`), `api/copilot` (schema 2.9), `data/`, `CLAUDE.md`.

## B.2 Your tiers

| Tier | You ship |
| --- | --- |
| **Core** | `sites.json` (8–9 real sites); `timeline_SITE.json` for every site with terrain horizon from LOLA; `grid_SITE.json` for one site; `scores.json` for one month; precomputed AI briefs |
| **Pro** | Sun-disk visible fraction; DSN coverage; grids for all sites; year-long `windows_SITE.json`; validation against NASA lighting maps and real CLPS landings; copilot API with tool calling and a numbers guard |
| **Insane** | Surface temperature context; finer grids; copilot that triggers new analyses |

**Decision points:** real timelines must reach `main` by **Sat 18:00** (minimum viable submission). If terrain horizons fight you, ship Horizons-only timelines with a flat horizon first (label it), then upgrade.

## B.3 Code layout (Python 3.11+)

```
data/
  sunchaser_data/
    horizons.py    JPL Horizons API client with caching
    dem.py         load LOLA DEMs, sample elevation, map projection helpers
    horizon.py     terrain horizon profiles by ray casting (with curvature)
    sunfrac.py     visible fraction of the Sun's disk
    dsn.py         Moon visibility from DSN complexes (Pro)
    timeline.py    builds timeline_SITE.json
    grid.py        builds grid_SITE.json (elevation, slope, sun_pct)
    windows.py     builds windows_SITE.json (Pro)
    scores.py      builds scores.json
    briefs.py      AI mission briefs + numbers guard
    validate.py    validation checks (Pro)
  cache/           downloaded DEMs and Horizons responses (gitignored)
  fake/            fake shared files for teammates on Saturday morning
  tests/
  run_all.py       one command: python data/run_all.py
api/
  copilot.js       Vercel serverless function (Node) or copilot.py (Python runtime)
vercel.json        includes shared/** in the function bundle
```

Libraries: `requests`, `numpy`, `rasterio` (GeoTIFF DEMs), `pyproj` (projections), `anthropic` (or the LLM SDK you use).

## B.4 Saturday 09:00: unblock the team (first 60 minutes)

1. Run the schema agreement meeting (`CLAUDE.md` Section 2). Get `rover.json` and `criteria.json` from Dhiran.
2. Commit **fake** `sites.json`, `timeline_site_a.json` (a week of hours), `grid_site_a.json` and `scores.json` to `data/fake/` and tell Dhiran to point his loaders at them; Harril makes his own fake grid.
3. Confirm everyone's branch, folder and that GitHub Desktop pushes work.

## B.5 Sites: `shared/sites.json`

- Use NASA's **Artemis III candidate landing regions** near the south pole (NASA published an updated list in October 2024; verify names on NASA's site). Regions on that list include names such as Malapert Massif, Haworth, Mons Mouton, Mons Mouton Plateau, Nobile Rim 1 and 2, de Gerlache Rim 2, Slater Plain and Peak near Cabeus B.
- Within each region pick one point on high, well-lit ground (use NASA's south-polar illumination maps to choose). Record lat, lon, elevation, source.
- Optional extra rows: the real landing sites of IM-1 (Feb 2024) and IM-2 (Mar 2025) for validation (look up published coordinates).

## B.6 Sun and Earth positions: JPL Horizons

- Endpoint: `https://ssd.jpl.nasa.gov/api/horizons.api` (no key).
- Observer on the lunar surface: `CENTER='coord@301'`, `COORD_TYPE='GEODETIC'`, `SITE_COORD='<east lon deg>,<lat deg>,<alt km>'`.
- Targets: `COMMAND='10'` (Sun), `COMMAND='399'` (Earth).
- `EPHEM_TYPE='OBSERVER'`, `QUANTITIES='4'` (apparent azimuth and elevation), `STEP_SIZE='1h'`, `START_TIME`/`STOP_TIME` for one year, `format='json'`. Parse the table between `$$SOE` and `$$EOE`.
- Verify parameter names and formats against the Horizons API documentation before running; cache every response to `data/cache/`.
- **Efficiency insight:** within a 2.5 km grid, the Sun's direction is the same for every cell (it's 150 million km away). Earth's direction shifts by under a tenth of a degree. So query once per site, not per cell.

## B.7 Terrain: LRO LOLA elevation

- Sources: NASA Goddard's Planetary Geodesy Data Archive (PGDA, e.g. https://pgda.gsfc.nasa.gov/products/69 for south-pole illumination and site topography) and LOLA polar stereographic DEMs (PDS Geosciences / Orbital Data Explorer). Download GeoTIFFs once to `data/cache/`.
- **Two resolutions (pro technique):** a high-resolution DEM (tens of metres or finer) for terrain within about 15–20 km, and a coarser polar DEM for distant terrain out to about 150 km, since distant mountains set the horizon for a low Sun.
- Use `pyproj` with the DEM's own projection (south polar stereographic) to convert lat/lon to map x/y.

## B.8 Terrain horizon by ray casting (`horizon.py`)

For an observer at map point P with ground height h0 plus mast height (use 2 m for a rover panel/antenna):

```
for each azimuth bin A (0.5° steps = 720 bins; 1° is fine for grid cells):
    direction = cos(A) * north_hat(P) + sin(A) * east_hat(P)      # in map x/y
    horizon(A) = -90°
    for distance d from one pixel out to D_max (step grows with distance, e.g. 1 pixel near, 1% of d far):
        h = elevation at P + d * direction (bilinear sample; switch to coarse DEM beyond ~15 km)
        drop = d² / (2 * 1737400)                                  # lunar curvature, metres
        angle = degrees(atan2(h - drop - (h0 + mast), d))
        horizon(A) = max(horizon(A), angle)
```

- **north_hat and east_hat:** azimuths from Horizons are measured from local north through east. Compute local north/east directions in map coordinates numerically: project (lat + δ, lon) and (lat, lon + δ) with pyproj and normalise. Don't hand-derive this at the pole.
- Vectorise with numpy (all distances for one azimuth at once).
- **Validation:** a site on a high ridge should have horizons near 0° or below in many directions; a site in a crater floor should have high horizons.

## B.9 Visible fraction of the Sun's disk (`sunfrac.py`)

Sun angular radius r ≈ 0.2666°. Let d = sun_elev − horizon_at_sun_az (treat the horizon as flat across the disk's width):

```
if d >= r:  frac = 1
elif d <= -r: frac = 0
else: frac = (r² · acos(-d / r) + d · sqrt(r² - d²)) / (π r²)
```

Checks: d = 0 → 0.5; d = r → 1; d = −r → 0. Write these as tests.

## B.10 Timelines: `shared/timeline_SITE.json`

For each site and each hour of the year:

- Sun and Earth az/el from Horizons; horizon heights at those azimuths (interpolate the 0.5° horizon profile); `sun_frac` from B.9; `earth_visible` = Earth elevation > Earth horizon.
- **DSN (Pro):** from each DSN complex (Goldstone ≈ 35.43°N 116.89°W, Madrid ≈ 40.43°N 4.25°W, Canberra ≈ 35.40°S 148.98°E), query the Moon's elevation with Horizons (observer `coord@399` at those coordinates, `COMMAND='301'`); a complex is available when the Moon is above 10°. Set `dsn_station` to an available complex name when `earth_visible`, else null.
- `surface_temp_k`: null unless Insane tier.
- One year at 1 hour is 8,760 rows; keep numbers to 2 decimals to stay around 1–2 MB per site.

**Fallback (if horizons aren't ready by Sat 16:00):** ship flat-horizon timelines (`sun_horizon_deg` = 0, `earth_horizon_deg` = 0), say so on the Methods page, upgrade later.

## B.11 Shadow grids: `shared/grid_SITE.json`

- 64 × 64 cells, 40 m each (2.56 km square) centred on the site, aligned with the polar stereographic map (document orientation in `orientation_note`).
- `elevation_m`: DEM sampled at cell centres. `slope_deg`: from elevation with central differences (degrees).
- `sun_pct[step][row][col]`: for each cell, a horizon profile; then for each hour in the window, `round(100 × sun_frac)` using the site's Sun az/el.
- **Performance:** distant terrain looks identical from every cell in a 2.5 km box, so compute the **far-field horizon (beyond ~15 km) once** for the grid centre and the **near-field horizon (within 15 km) per cell**, then take the max. Use 1° bins for cells.
- Window: 14 days (336 steps). **Pick a dramatic window with Harril**: one where a shadow crosses the area so the shortest route freezes and the Sunchaser route survives. Scan candidate windows and share options.
- Size check: 336 × 64 × 64 integers ≈ 1.4 M values; keep JSON compact (no spaces) and Vercel serves it compressed.

## B.12 Landing windows: `shared/windows_SITE.json` (Pro)

For each site, for landing times every 6 hours across the year:

- Take `mission_length_days × 24` timeline rows from the landing time.
- Per 24-hour day: sun hours = hours with `sun_frac ≥ 0.5`; contact hours = hours with `earth_visible`; the day is usable if both meet `criteria.usable_day`.
- `usable_days` = count of usable days; `sun_hours`, `contact_hours`, `both_hours` = totals; `longest_dark_h` = longest run with `sun_frac < 0.5`; `survives` = `longest_dark_h ≤ max_dark_spell_hours`.
- This feeds Dhiran's heatmap and the cost-of-a-slip chart.

## B.13 Scores: `shared/scores.json`

- Window: one month (agree it with Dhiran; e.g. the month with the most interesting spread between sites).
- For each site: the best landing time within the month (max usable days, tie-break on shorter longest dark spell), its metrics, and `survives`.
- Rank by usable days, then longest dark spell, then contact hours.
- Add the AI `brief` (B.14).

## B.14 AI mission briefs (`briefs.py`)

- For each site, send the computed metrics as JSON to an LLM with a fixed prompt: "Write three sentences for a mission manager using only these numbers. Mention the best landing time, usable days and the main risk." Temperature low.
- **Numbers guard (impressive and important):** extract every number from the generated brief with a regex and check each one appears in (or rounds from) the input facts. If any doesn't, regenerate or fall back to a template sentence. Mention this on the Methods page: "AI text is checked so it can't invent numbers."
- Briefs are generated offline and saved in `scores.json`, so no API key is needed in the website for Core.

## B.15 Copilot API: `api/copilot` (Pro)

- Vercel serverless function at `/api/copilot` (Node is simplest on Vercel; Python runtime also works).
- Bundle the data: in `vercel.json`, configure the function with `includeFiles: "shared/**"` so it can read the JSON at runtime (check Vercel's current docs for the exact config).
- LLM with **tool use**. Tools, each answered by your code from the JSON:
  - `get_site_summary(site)` → scores row + site info
  - `find_windows(site, month, min_usable_days)` → matching rows from `windows_SITE.json`
  - `compare_sites(sites, month)` → side-by-side metrics
  - `timeline_stats(site, start, end)` → % sunlit, % contact, longest dark spell
  - `slip_cost(site, landing, budget)` → cost per usable day for slips of 0–7 days
- System prompt: answer only from tool results; if data doesn't cover the question, say so.
- Response: `{answer, facts_used: [{label, value}]}` built from the tool results actually used.
- API key in a Vercel environment variable (tell Dhiran the variable name). Add a simple rate limit or a cap on question length.

## B.16 Validation (Pro: this is what makes judges trust you)

1. **Against NASA lighting maps:** for each site, your yearly % of hours with `sun_frac ≥ 0.5` versus the illumination percentage in NASA's south-polar illumination map (Moon Trek layer or PGDA product) at the same point. Report the differences in a small table on the Methods page.
2. **Against real landings:** run the timeline at the IM-1 (Feb 2024) and IM-2 (Mar 2025) landing sites and dates; check that the Sun was up and Earth visible when they landed and operated (they communicated with Earth). Report it honestly, including any mismatch.
3. **Physics sanity:** Sun elevation at sites near the pole stays within about ±1.5° of the flat horizon; Earth elevation varies by about ±7° over a month.

## B.17 Tech-lead duties

- Commit `CLAUDE.md` to the repo root (it doubles as `PROJECT.md`).
- At Sat 12:00, Sat 18:00 and Sun 10:00: merge pull requests in order data → planner → web on github.com; resolve conflicts; tell everyone to **Update from main**.
- Keep `main` deployable: Dhiran's Vercel builds from `main`.
- Own the README skeleton (problem, live link, modules, results, data sources, AI use, team), and fill in your section: data sources, horizon method, validation results.
- Sunday 13:00 feature freeze: only fixes.

## B.18 Your weekend schedule

| When | Goal |
| --- | --- |
| Sat 09:00–10:00 | Schema meeting; fake files committed; everyone unblocked |
| Sat 10:00–12:00 | Sites chosen; Horizons client with caching; first raw timeline (flat horizon) |
| **Sat 12:00** | **Checkpoint:** merge all three branches |
| Sat 12:00–16:00 | DEM loading, horizon ray casting, sun fraction; terrain-aware timelines |
| Sat 16:00–18:00 | All site timelines; Earth visibility; quick sanity plots |
| **Sat 18:00** | **Checkpoint:** real timelines on main (minimum viable submission) |
| Sat 18:00–24:00 | Shadow grid for the demo site (dramatic window agreed with Harril); scores; briefs. Then sleep. |
| Sun 08:00–10:00 | Landing windows; grids for more sites; DSN |
| **Sun 10:00** | **Checkpoint:** windows, scores, grids, briefs on main |
| Sun 10:00–13:00 | Copilot API; validation table; README |
| **Sun 13:00** | **Feature freeze:** fixes, help with video, submit |

## B.19 Prep before the event (learning only)

- [ ] Commit `CLAUDE.md` and the two handbooks to the repo (e.g. `docs/`), and send each teammate their handbook.
- [ ] Confirm registration and team formation on the Space Apps site; read the rules (build window, AI use).
- [ ] Read the full challenge statement.
- [ ] In a throwaway notebook: one Horizons query for a south-pole point; plot a week of Sun elevation.
- [ ] Download one LOLA south-pole DEM and open it with rasterio; plot it.
- [ ] Have Claude explain horizon ray casting and the Sun-disk formula until you can explain them back.
- [ ] Practise one Vercel serverless function in a throwaway project.

## B.20 Done means

- [ ] `sites.json`, all `timeline_*.json`, at least one `grid_*.json`, `scores.json` with briefs on `main`, matching schemas exactly.
- [ ] Pro: `windows_*.json`, validation table, copilot live.
- [ ] Tests for sun fraction, curvature drop and horizon sanity pass.
- [ ] README data section written.

## B.21 Interview questions you must be able to answer

1. How do you compute whether a spot at the south pole sees the Sun, including terrain and curvature?
2. Why model the Sun's disk fraction instead of up/down?
3. Why can you compute the Sun's direction once per site but horizons per cell?
4. How did you validate your lighting results?
5. How does the copilot avoid inventing numbers?
6. How did you keep three people's work compatible? (Schemas, fake data, branches, checkpoints.)

---

# Part C: Reference

## C.1 All 14 challenges (objectives paraphrased) and our solution ideas

| # | Challenge | Level | Objective | Our idea |
| --- | --- | --- | --- | --- |
| 1 | Abandoned but not Forgotten | Beg/Int | Tell school-age fans the story of NASA hardware left on the Moon, Mars and deep space, and the science it enabled | 3D globes of every artifact, chapter stories, kids find landers in real LROC/HiRISE photos |
| 2 | Be An Earth System Trend Detective! | Advanced | Find NASA-measured/modelled variables, visualise change, decide what/where/how much and whether significant | Per-pixel Mann-Kendall + Sen's slope with false-discovery-rate correction; opposite-trend case files |
| 3 | Build a Junior Astronaut Mission Trainer | Beg/Int | Game where students run a lunar/Martian outpost balancing life support, shielding, power, food | Linked-systems outpost sim, real DONKI flares, predict-then-see turns, NASA life-support baseline numbers |
| 4 | **Lunar Landing Site Navigator** (formerly CLPS Lunar Mission Browser) | Int/Adv | Compare south-pole landing sites and dates by Sun and Earth above the horizon (power and comms) | **Sunchaser (chosen)** |
| 5 | Create Health Monitoring Software for Astronauts | Intermediate | Software for astronauts to track radiation, bone, heart and behavioural risks and act | Personal-baseline anomaly detection, radiation vs career limits, comms-delay action cards |
| 6 | Dancing with the SARs | Int/Adv | Use NASA-ISRO NISAR radar to track and visualise surface change | Flood/subsidence through clouds, log-ratio change detection, InSAR motion |
| 7 | Field Shift: Adapting Farms with NASA Data | Int/Adv | Decision tool combining NASA data with local soil/crop/farmer priorities to choose rotations; compare ≥3 incl. current | FAO-56 water balance on POWER/SMAP/ECOSTRESS/GPM; backtest rotations |
| 8 | Flame in Freefall (AI-powered fire safety, microgravity combustion) | Int/Adv | AI dashboard summarising, ranking and explaining decades of NASA microgravity combustion results for Moon/Mars fire safety | LLM extraction of experiments with citations, ranked findings, abstaining Q&A, published eval |
| 9 | Harmonization of MODIS and VIIRS Hot Spots | Int/Adv | Merge two decades of MODIS/VIIRS fire detections into one record; web app with a burning calendar for any area | Common grid, overlap-period calibration with uncertainty, calendar + anomalies |
| 10 | Identify Earth Locations that Analog the Moon Base Locations and Mars | All | Use open data to identify and characterise new Earth analogs | Same-measure fingerprints on three worlds, similarity ranking, validation score |
| 11 | Interplanetary Survival Guide: Martian Map | Intermediate | Layered Mars view combining missions to plan a safe, science-rich Marswalk | Jezero HiRISE slopes, A* routes, suit O₂ budget, CRISM science stops |
| 12 | Planet X and SPHEREx | Advanced | Public tool showing SPHEREx all-sky images so movers (asteroids, comets, brown dwarfs) are easy to see | Wavelength-matched differencing, track linking, recall vs JPL catalogue |
| 13 | Space Mission Design Game | Beg/Int | Game to design, run and simulate a mission trading objectives, instruments, launcher, budget, power, mass, comms | Real physics levels based on real missions; "did you beat NASA?" |
| 14 | The Earth Information Jukebox | Beg/Int | Pair NASA Earth Information Center visuals with real-time sound | Variable-to-instrument sonification, accessibility mode, listening test |

## C.2 Competitive landscape for our challenge (public GitHub, seen Nov 1)

Projects such as LunaHorizon, LunarWindow, SeleneSight, LunarSite Compass, BroBYW's CLPS Lunar Mission Website and a Streamlit browser from Málaga already compare south-pole sites and dates; some use real LOLA horizons, DSN contact and power calculators. **None seen** had a rover energy model, sun-chasing route planning with survival probability, a year-long landing-window business case, or a grounded copilot. Our edge is decisions (where, when, how to drive, what it's worth), not just lighting charts. Match their rigour on the core (terrain horizons, validation) so the extras land.

## C.3 Approved text

**Tagline:** Sunchaser by Team Zenon: where to land on the Moon, when, and how to keep your robot alive.

**Pitch:** "At the Moon's south pole the Sun skims the horizon. Land in the wrong spot or drive the wrong way and your robot freezes. Sunchaser tells you where to land, when, and how to drive, and proves it with NASA data."

**Team page text (doesn't reveal the idea):**

> Team Zenon is taking on the Lunar Landing Site Navigator challenge at NASA Space Apps 2026. The Moon's south pole is where the next wave of commercial and Artemis missions is heading, and it's one of the hardest places in the solar system to operate: the Sun barely rises, shadows never stop moving, and every hour of light matters. We're building a tool that helps lunar missions make smarter decisions about where to go and when, using real NASA data on lighting, terrain and communication. Our approach mixes engineering, robotics, AI and a business mindset, because getting to the Moon is only half the problem. Staying useful once you're there is the other half.

## C.4 Data sources

| Source | Use | Access |
| --- | --- | --- |
| JPL Horizons API (ssd.jpl.nasa.gov/api/horizons.api) | Sun, Earth, Moon positions from any point | No login |
| NASA Goddard PGDA (pgda.gsfc.nasa.gov, e.g. product 69) | South-pole illumination maps and site topography | No login |
| LRO LOLA DEMs via PDS Orbital Data Explorer (oderest.rsl.wustl.edu) | Terrain elevation | No login |
| NASA Moon Trek WMTS (trek.nasa.gov) | South-pole illumination and Earth-visibility map layers | No login, works in browser |
| NAIF SPICE (naif.jpl.nasa.gov) | Offline geometry alternative to Horizons | No login, more setup |
| ShadowCam (pds.shadowcam.im-ldi.com) | Images inside permanently shadowed regions | No login |
| Space Data Atlas (spacedata.swapniltamse.com) | Curated datasets and starter code per challenge (third party) | Open |

## C.5 GitHub Desktop quick reference

- Teammates: **File → Clone repository** → `sunchaser` → **Current Branch** → their branch → work → **Commit to <branch>** → **Push origin**.
- Checkpoints: **Branch → Create Pull Request** (base `main`), Baldwin merges data → planner → web.
- After merges: **Fetch origin** → **Branch → Update from main** → **Push origin**.
- Empty-file troubleshooting: check you're viewing the right branch; save files in VS Code (white dot = unsaved; turn on Auto Save); make sure VS Code is open on the repo folder (**Repository → Show in Explorer**); check **History** for the commit and that it was pushed.

## C.6 Files produced in the chat

| File | For | Contents |
| --- | --- | --- |
| `CLAUDE.md` | Repo root, everyone | Project brief, physics, tiers, full data contract, Git workflow, rules |
| `plan-robotics.md` | Harril | Standalone handbook: everything in CLAUDE.md + full robotics build guide |
| `plan-engineering-business.md` | Dhiran | Standalone handbook: everything in CLAUDE.md + full engineering, business and web build guide |
| `HANDOFF-baldwin.md` | Baldwin | This file |
| Claude Doc "Space Apps 2026: Challenge Playbook" | Baldwin | All 14 challenges scored; earlier, simpler Sunchaser plan (superseded) |
