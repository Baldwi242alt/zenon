# Sunchaser

**Where to land on the Moon, when, and how to keep your robot alive.**
Team Zenon · NASA Space Apps Challenge 2026 · challenge: *Lunar Landing Site Navigator*

> At the Moon's south pole the Sun skims the horizon. Land in the wrong spot or drive the wrong way and
> your robot freezes. Sunchaser tells you where to land, when, and how to drive, and proves it with NASA data.

## The problem

NASA's Commercial Lunar Payload Services (CLPS) program is sending commercial landers and rovers to the lunar
south pole. There the Sun never rises more than about 1.5° above a flat horizon, so every hill casts a
shadow kilometres long that moves hour by hour, and Earth, the only link home, dips behind the terrain for
days at a time. Sunlight is power and warmth; Earth in view is communication. A poor site, a poor landing
date or a poor route means fewer working days, or a dead robot.

The challenge asks for a tool to compare south-pole landing sites and dates by when the Sun and Earth are
above the local horizon. Sunchaser does that with real terrain, then goes further: it scores every landing
time in a year, plans rover routes that survive the moving shadows, and puts a number on the risk.

## What it does

| Module | What it does | Owner |
| --- | --- | --- |
| Light and comms engine | Hour-by-hour Sun and Earth visibility for 9 NASA Artemis III candidate regions, from JPL Horizons ephemerides and terrain horizons ray-cast on LRO LOLA elevation data out to 150 km, with lunar curvature and the visible fraction of the Sun's disk | Baldwin |
| Landing window scanner | Scores every landing time across 2027 (every 6 hours) by usable mission days and survivability | Baldwin |
| Shadow grids | Per-cell sunlight, hour by hour, over a 5.1 km operations area at each site | Baldwin |
| Deep Space Network coverage | Which of Goldstone, Madrid and Canberra can see the Moon each hour | Baldwin |
| Surface temperature | 1D regolith heat model (Hayne et al. 2017 properties) on each site's own slope | Baldwin |
| Rover energy physics | Solar input, avionics, heaters, drive power from slope and rolling resistance, battery | Harril |
| Sun-chasing planner | Space-time A\* with a battery constraint and dominance pruning; Monte Carlo survival probability; fast-versus-safe routes; replanning after a fault | Harril |
| Hardware-in-the-loop | Arduino rover whose light sensor drives the same battery simulation | Harril |
| Mission copilot | Answers questions from the computed data only; every number is checked against the data before it is shown | Baldwin |
| Engineering specs, business model, web app | Rover specifications and usable-day criteria, cost per usable mission day and cost of a launch slip, and the website | Dhiran |

## Headline results

<!-- RESULTS:START -->
**Where and when to land** (best landing in June 2027, 10-day mission; year-round light and contact):

| Rank | Site | Best landing | Usable days | Sunlit, 2027 | Earth in view, 2027 | Landings the rover survives, 2027 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Peak near Cabeus B | 19 Jun 18:00 UTC | 10 of 10 | 52% | 69% | 24% |
| 2 | de Gerlache Rim 2 | 22 Jun 06:00 UTC | 10 of 10 | 77% | 53% | 45% |
| 3 | Haworth | 21 Jun 06:00 UTC | 10 of 10 | 66% | 55% | 32% |
| 4 | Mons Mouton | 16 Jun 12:00 UTC | 8 of 10 | 76% | 73% | 48% |
| 5 | Slater Plain | 1 Jun 00:00 UTC | 6 of 10 | 58% | 32% | 29% |
| 6 | Malapert Massif | 13 Jun 18:00 UTC | 5 of 10 | 68% | 71% | 37% |
| 7 | Nobile Rim 2 | 8 Jun 06:00 UTC | 3 of 10 | 51% | 61% | 23% |
| 8 | Mons Mouton Plateau | 10 Jun 12:00 UTC | 0 of 10 | 41% | 57% | 14% |
| 9 | Nobile Rim 1 | 27 Jun 12:00 UTC | 7 of 10 (not survivable) | 81% | 62% | 54% |

Across the year only 14-54% of landing times are survivable, depending on the site: *when* you land matters as much as *where*.

**How to drive** (a 4-5 km traverse at each site; survival = share of 500 Monte Carlo runs in which the rover never froze, on the way or in the 24 hours parked at the destination):

| Site | Shortest route | Sunchaser (fastest safe) | Sunchaser (max margin) |
| --- | --- | --- | --- |
| Peak near Cabeus B | arrives in 20.0 h, survival 2% | arrives in 24.6 h, survival 95% | arrives in 30.3 h, survival 100% |
| Haworth | **freezes** after 19.8 h, survival 33% | arrives in 22.5 h, survival 100% | the fastest safe route is already the safest found |
| Malapert Massif | arrives in 23.5 h, survival 71% | arrives in 23.5 h, survival 80% | the fastest safe route is already the safest found |
| Mons Mouton Plateau | **freezes** after 16.0 h, survival 1% | arrives in 24.4 h, survival 100% | arrives in 24.7 h, survival 100% |
| Mons Mouton | **freezes** after 16.5 h, survival 3% | arrives in 20.6 h, survival 97% | the fastest safe route is already the safest found |
| Nobile Rim 1 | **freezes** after 15.7 h, survival 5% | arrives in 19.6 h, survival 100% | the fastest safe route is already the safest found |
| Nobile Rim 2 | **freezes** after 20.1 h, survival 0% | arrives in 26.1 h, survival 96% | arrives in 28.1 h, survival 100% |
| de Gerlache Rim 2 | **freezes** after 16.5 h, survival 0% | arrives in 23.4 h, survival 100% | the fastest safe route is already the safest found |
| Slater Plain | **freezes** after 17.1 h, survival 10% | arrives in 20.5 h, survival 100% | the fastest safe route is already the safest found |

At 7 of 9 sites the shortest route freezes in the scenario found by searching 2027; the sun-chasing route arrives every time. These are real windows of 2027 found by search, not staged cases: `planner/find_scenarios.py`.

<!-- RESULTS:END -->

All of the above use the placeholder rover and criteria from the project brief (`CLAUDE.md` 2.6 and 2.7)
until `shared/rover.json` and `shared/criteria.json` are committed; the pipelines say so when they run, and
one command each regenerates everything with the real values.

## How we know it's right

- **Against NASA's published illumination maps** (LOLA team, Mazarico et al. 2011, updated 2016): our
  18.6-year average Sun and Earth visibility at the 9 sites correlates **0.978** (Sun) and **0.987** (Earth)
  with NASA's maps. The remaining gap is explained and measured: a 2 m mast versus ground level moves the
  result by about 14 points, and NASA's map sits between the two.
- **Against real landings:** at the IM-1 (Feb 2024) and IM-2 (Mar 2025) landing sites and times, the model
  shows the Sun up and Earth in view, as both landers needed to communicate. One mismatch is reported openly:
  IM-1 shut down 2.5 days before our terrain sunset, with the Sun still about 5° up; the lander had come
  to rest tilted on its side.
- **Against Diviner temperatures:** the heat model gives 385 K at equatorial noon and 92 K before dawn; LRO
  Diviner measured about 390 K and 95 K.
- **Against brute force:** the planner's pruned search arrives at exactly the same time as an unpruned search
  on small random worlds.
- **Against the ephemeris:** the Sun's azimuth turns once per 29.53 days and stays within the Moon's 1.54°
  axial tilt (plus the site's distance from the pole); Earth's elevation swings by ±6.8° (libration).
- **Tests:** `python -m pytest data/tests planner/tests hardware/tests` (hand-checkable cases throughout).

Details, tables and the limits of each check are in [`data/README_data.md`](data/README_data.md).

## Data sources (all NASA, all free, no login)

| Source | Used for |
| --- | --- |
| [JPL Horizons API](https://ssd.jpl.nasa.gov/api/horizons.api) (DE441 ephemeris) | Sun and Earth azimuth/elevation at each site every hour; the Moon's elevation at each DSN complex |
| [LRO LOLA polar elevation models](https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/) (20 m, 30 m, 120 m) | Terrain heights, slopes and horizons |
| [LOLA illumination maps](https://pgda.gsfc.nasa.gov/products/69), NASA Goddard PGDA | Validation of Sun and Earth visibility |
| [NASA's Artemis III candidate regions](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/) (Oct 2024) | The 9 regions |
| Candidate landing points, JGR Planets 2025, doi:10.1029/2025JE009434 | 77 published points inside those regions; we keep the best-lit one per region |
| Hayne et al. 2017, JGR Planets 122, 2371, and the open-source `heat1d` model | Regolith thermal properties |
| NASA/LROC IM-1 and IM-2 landing coordinates | Validation against real landings |

## Repository

```
shared/      the data contract: sites, timelines, windows, grids, scores, routes (JSON, one owner per file)
data/        Baldwin: data pipeline (Python)             -> data/README_data.md
api/         Baldwin: mission copilot (Vercel function)  -> api/README.md
planner/     Harril: rover physics and planners (Python) -> planner/README_planner.md
hardware/    Harril: Arduino rover and laptop bridge     -> hardware/README.md
web/         Dhiran: web app
CLAUDE.md    project brief and the exact shared data formats
docs/        each member's handbook
```

## Run it

```bash
pip install -r data/requirements-pipeline.txt
python -m pytest data/tests planner/tests hardware/tests      # everything, about 15 seconds

# Rebuild the data (needs about 4 GB of LOLA elevation files; download commands in data/README_data.md)
python data/build_sites.py && python data/build_timelines.py
python data/build_windows.py && python data/build_scores.py
python data/build_grid.py --year && python planner/find_scenarios.py && python data/build_grid.py --from-scenarios
python planner/run.py --all
python data/validate.py

# Ask the copilot without any API key (rule-based fact finder)
python -c "import importlib.util as u; s=u.spec_from_file_location('c','api/copilot.py'); c=u.module_from_spec(s); s.loader.exec_module(c); print(c.answer_without_ai('Does the rover survive at Slater Plain?')['answer'])"

# Replay a planned route through the hardware bridge without a rover
python hardware/bridge.py --site slater_plain --simulate --fast
```

## Honest limits

- Rover specifications and usable-day criteria are placeholders until the engineering lead's sourced values land.
- Terrain is LOLA at 20 m near each site and 120 m beyond 15 km; rocks and craters smaller than that are not seen
  (IM-2 came to rest in a 20 m crater no orbital map resolves).
- The observer is a 2 m mast; a taller lander sees more Sun.
- The shadow grids use 80 m cells and hourly steps.
- The planner's rover has no wheel slip, an on/off heater and no comms power while driving.
- Surface temperatures ignore heat from surrounding terrain, so shadowed hours read too cold.
- Everything is computed for 2027.

## How we used AI

We used AI coding assistants (Claude Code, and others via the handbooks in `docs/`) to help write, test and
document the code, working from our own design, physics references and data contract in `CLAUDE.md`.
Results were checked against hand-worked cases, NASA's published maps and real landings rather than trusted.
Inside the product, the mission copilot can use an LLM (Google Gemini's free tier) to choose which data tool
to call and to phrase the answer, but a numbers guard rejects any answer containing a number that is not in
the computed data, and a rule-based fact finder with no AI answers when no model is available.

## Team Zenon

- **Baldwin**: data, AI and tech lead
- **Harril**: robotics lead
- **Dhiran**: engineering and business lead
