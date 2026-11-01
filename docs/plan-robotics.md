# Sunchaser: Robotics Lead Handbook

**Team Zenon · NASA Space Apps Challenge 2026 · November 14–15, 2026**
**Owner:** Harril (robotics lead) · **Branch:** `planner-(Harril)` · **You write in:** `planner/`, `hardware/`, `shared/route_*.json`

> **How to use this file:** paste this entire file into your AI assistant at the start of every session, then tell it what you're working on. It's written so the AI knows the full project, the exact data formats, what you own, and how good the result has to be. If you finish everything here, you've built one third of Sunchaser.

---

## 0. Brief for the AI assistant

You are helping **Harril**, the **robotics lead** on Team Zenon, a three-person team building **Sunchaser** during the 48-hour NASA Space Apps Challenge 2026 (November 14–15, 2026). The official challenge is **"Lunar Landing Site Navigator"** (formerly "CLPS Lunar Mission Browser"): build an easy tool to compare lunar south-pole landing sites and dates, showing when the Sun and Earth are above the local horizon, so planners can judge solar power and direct-to-Earth communication windows.

Sunchaser goes far beyond that minimum. It is a mission-planning platform for commercial lunar missions that:

1. Computes **terrain-aware sunlight and Earth visibility** for each candidate south-pole site, hour by hour, from real NASA ephemerides (JPL Horizons) and real terrain (LRO LOLA elevation data), including the fraction of the Sun's disk above the terrain.
2. Scans **every possible landing time** across a year and scores it by usable mission days.
3. Simulates a **rover's energy budget** from first-principles physics (solar input, avionics, heaters, drive power from slope and rolling resistance).
4. Plans **sun-chasing rover routes** with space-time A\* search that keeps the rover alive as shadows move, compares them with the naive shortest route, and quantifies risk with **Monte Carlo survival probability**.
5. Turns it into a **business case** (cost per usable mission day, cost of a launch slip) and an **AI mission copilot** that answers questions using only the computed data.
6. Presents everything in a polished web app with a map, timelines, a landing-window heatmap, 2D and 3D rover playback, and a business dashboard.

**Team and ownership (strict):**

| Person | Role | Branch | Writes only in |
| --- | --- | --- | --- |
| Baldwin | Data, AI and tech lead | `data-(Baldwin)` | `data/`, `api/`, `PROJECT.md`, and the shared files he owns |
| Harril | Robotics lead | `planner-(Harril)` | `planner/`, `hardware/`, and `shared/route_*.json` |
| Dhiran | Engineering and business lead | `web-(Dhiran)` | `web/`, `shared/rover.json`, `shared/criteria.json` |

**Rules for the AI (follow every one):**

1. **Only write code in Harril's folders.** Never edit another person's folder. If something there needs to change, write a short message Harril can send to its owner.
2. **The shared JSON files must match Section 2 exactly:** field names, types, units, array orders. If you believe a schema should change, say so explicitly; never change it silently.
3. **Real physics, real NASA data.** Never present an invented number as a fact. Anything estimated is labelled "estimate" in code comments and in the output.
4. **Build in tiers: Core → Pro → Insane.** Do not start a higher tier until the lower tier works end to end, is tested, and is committed. A finished Core beats a half-built Insane.
5. **Readable, commented code.** After writing a function, explain it to Harril in plain language. Harril must be able to explain every part in a job interview.
6. **Test with hand-checkable cases** before running on real data (tiny grids, simple numbers you can verify by hand).
7. **Conventions:** times are ISO 8601 UTC strings ending in `Z`; angles in degrees; distances in metres; power in watts (W); energy in watt-hours (Wh); percentages as 0–100 unless a field says fraction (0–1).
8. **Performance matters:** website data files should stay small (a few MB per site at most); Python should finish each run in minutes, not hours.
9. **Be honest about limits.** Every output that simplifies reality says so in one line.

---

## 1. The project

### 1.1 The challenge

**Lunar Landing Site Navigator:** https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/

What NASA asks for: an easy tool for comparing lunar south-pole landing sites and dates, showing where the Sun and Earth sit above the horizon so planners can judge solar power and direct-to-Earth communication windows. Judges score against that brief first, so **the site and date comparison must be excellent**, and everything else builds on it.

### 1.2 The physics of the lunar south pole

Everyone on the team, and every AI, should know these:

- **The Sun barely rises.** The Moon's spin axis is tilted only about 1.5° from the plane of Earth's orbit, so at the pole the Sun never climbs more than about 1.5° above a flat horizon. It circles the sky, skimming the edge.
- **The Sun is a disk, not a point.** It's about 0.53° wide. Near the horizon, terrain often hides part of it, so we model the **visible fraction of the Sun's disk (0–1)**, not just "up or down".
- **Shadows are enormous and slow.** One lunar day (sunrise to sunrise) lasts about 29.5 Earth days. A hill can shade a spot for hours to many days, while a ridge nearby stays lit almost continuously.
- **Earth wobbles on the horizon.** Because of libration, Earth's elevation at the south pole swings by roughly ±6.7° over the month. At many sites, terrain blocks Earth for days at a time, cutting direct-to-Earth contact.
- **Curvature matters for distant terrain.** The Moon's radius is 1,737.4 km, so distant ground drops below a flat line by about d² ÷ (2R): roughly 29 m at 10 km and 720 m at 50 km. A horizon calculation that ignores this is wrong.
- **Gravity is 1.62 m/s²** (one sixth of Earth's).
- **Sunlight at the Moon** delivers about 1,361 W per square metre.
- **The cold is lethal.** Shadowed ground gets extremely cold; rovers need heaters to survive darkness, and heaters drain batteries. At walking pace, keeping warm usually costs more energy than climbing hills.
- **Solar panels are vertical.** Because the Sun is on the horizon, south-pole rovers and landers use vertical (often sun-tracking) panels, not flat ones on top.
- **Communication** goes direct to Earth via NASA's Deep Space Network (dishes at Goldstone in California, Madrid in Spain and Canberra in Australia), so the site must see Earth, and at least one complex must see the Moon.

### 1.3 The business context

- NASA's **Commercial Lunar Payload Services (CLPS)** program pays private companies, such as Intuitive Machines, Astrobotic and Firefly Aerospace, to deliver robots and experiments to the Moon. Real CLPS landers have already landed near the south pole (Intuitive Machines' IM-1 in February 2024 and IM-2 in March 2025).
- Every mission has a fixed budget and a limited number of working days on the surface. At the south pole, a poor site, a poor landing date, or a poor route means fewer useful days or a dead robot.
- **The customer question Sunchaser answers:** "For our budget, where and when should we land to get the most working days, and how do we keep our rover alive?"

### 1.4 The product: Sunchaser

**Pitch:** "At the Moon's south pole the Sun skims the horizon. Land in the wrong spot or drive the wrong way and your robot freezes. Sunchaser tells you where to land, when, and how to drive, and proves it with NASA data."

| Module | What it does | Owner |
| --- | --- | --- |
| Light and comms engine | Hour-by-hour Sun and Earth visibility per site, terrain-aware | Baldwin |
| Shadow grid | Per-cell sunlight over a local area around each site | Baldwin |
| Landing window scanner | Scores every landing time across a year | Baldwin |
| Rover energy physics | Solar input, avionics, heaters, drive power, battery | Harril |
| Sun-chasing planner | Space-time A\*, Monte Carlo survival, fast-vs-safe routes | Harril |
| Hardware-in-the-loop rover | A real Arduino rover whose light sensor feeds the battery sim | Harril |
| Engineering specs and criteria | Rover numbers with sources; what counts as a usable day | Dhiran |
| Business model | Cost per usable day, cost of a launch slip | Dhiran |
| Web app | Map, timelines, heatmap, 2D/3D rover ops, dashboard, copilot chat | Dhiran |
| AI | Mission briefs and the mission copilot (answers from computed data only) | Baldwin |

### 1.5 Tiers: what "done" looks like at each level

| Area | Core (must ship) | Pro (impressive) | Insane (stretch) |
| --- | --- | --- | --- |
| Light and comms (Baldwin) | Horizons Sun/Earth per site + terrain horizon from LOLA | Sun-disk visible fraction; DSN coverage | Surface temperature context |
| Shadow grid (Baldwin) | One site, per-cell sunlight from terrain ray-casting | All sites | Finer resolution, longer window |
| Landing windows (Baldwin) | Scores per site for one month | Year-long landing heatmap | Replay of real landings as validation |
| AI (Baldwin) | Precomputed mission briefs | Copilot with tool calling over the data | Copilot that triggers new analyses |
| Rover physics (Harril) | Battery sim: solar in, avionics + heaters out | Drive power from slope and rolling resistance; partial sun | Thermal-dependent heater power |
| Planner (Harril) | 2D A\* shortest route + simulation | Space-time A\* with battery; Monte Carlo survival | Fast-vs-safe Pareto routes; replanning |
| Hardware (Harril) | — | — | Arduino rover with light sensor driving the live battery sim |
| Specs and business (Dhiran) | `rover.json`, `criteria.json` with sources; cost per usable day | Cost of a launch slip | Sensitivity analysis |
| Web app (Dhiran) | Map, timeline, 2D rover playback, dashboard | Landing heatmap, compare mode, copilot chat, Methods page | 3D terrain with live shadows and the rover driving |

### 1.6 How the pieces connect

```
Dhiran ──► shared/rover.json ─────────────────────────► Harril (energy model)
Dhiran ──► shared/criteria.json ──────────────────────► Baldwin (scores, windows)
Baldwin ─► shared/sites.json ─────────────────────────► everyone
Baldwin ─► shared/timeline_SITE.json ─────────────────► Dhiran (timeline), Harril (comms context)
Baldwin ─► shared/grid_SITE.json ─────────────────────► Harril (planning), Dhiran (2D/3D playback)
Baldwin ─► shared/windows_SITE.json ──────────────────► Dhiran (heatmap, cost of slip)
Baldwin ─► shared/scores.json ────────────────────────► Dhiran (dashboard)
Harril ──► shared/route_SITE.json ────────────────────► Dhiran (rover ops)
Baldwin ─► api/copilot (serverless function) ─────────► Dhiran (chat UI)
```

**Each shared file has exactly one owner who writes it. Everyone else only reads it.** That's what keeps merges clean.

### 1.7 What makes this impressive (say these in the pitch)

1. **Real terrain physics**, not a flat-horizon shortcut: horizons ray-cast from LOLA elevation with lunar curvature, and the partial Sun disk.
2. **Validated:** cross-checked against real CLPS landings and NASA's published illumination maps.
3. **Uncertainty, not false precision:** survival is a probability from Monte Carlo runs, not a yes/no.
4. **Decisions, not just data:** the best landing window, the best route, and what a slip costs in money.
5. **Grounded AI:** the copilot only answers from computed numbers and shows which facts it used.

---

## 2. The shared data contract

All files live in `shared/`. Agree these in the first hour on Saturday. **Until the real files exist, every consumer builds on fake files with exactly the same shape**, so nobody waits. Example values below are placeholders.

### 2.1 `shared/sites.json` (owner: Baldwin)

```json
[
  {
    "id": "site_a",
    "name": "Example Ridge",
    "lat": -89.45,
    "lon": 137.3,
    "elevation_m": 1850,
    "source": "NASA Artemis III candidate regions",
    "notes": "Ridge with near-continuous light"
  }
]
```

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Short id used in filenames (`timeline_site_a.json`) |
| `name` | string | Display name |
| `lat`, `lon` | number | Degrees (south is negative latitude) |
| `elevation_m` | number | Terrain height from LOLA |
| `source` | string | Where the site comes from |
| `notes` | string | One line for the map card |

### 2.2 `shared/timeline_SITE.json` (owner: Baldwin), one row per hour for a full year

```json
{
  "site": "site_a",
  "start": "2027-01-01T00:00Z",
  "step_h": 1,
  "rows": [
    {
      "time": "2027-01-01T00:00Z",
      "sun_elev_deg": 0.84,
      "sun_az_deg": 212.4,
      "sun_horizon_deg": 0.31,
      "sun_frac": 0.72,
      "earth_elev_deg": 4.10,
      "earth_az_deg": 11.0,
      "earth_horizon_deg": 1.20,
      "earth_visible": true,
      "dsn_station": "Canberra",
      "surface_temp_k": null
    }
  ]
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `sun_elev_deg`, `sun_az_deg` | number | Sun's position from JPL Horizons (azimuth from local north through east) |
| `sun_horizon_deg` | number | Terrain horizon height in the Sun's direction |
| `sun_frac` | number 0–1 | Fraction of the Sun's disk above the terrain |
| `earth_elev_deg`, `earth_az_deg` | number | Earth's position from JPL Horizons |
| `earth_horizon_deg` | number | Terrain horizon height in Earth's direction |
| `earth_visible` | bool | Earth's centre above the terrain horizon |
| `dsn_station` | string or null | Pro: a DSN complex that can see the Moon (null if none or not computed) |
| `surface_temp_k` | number or null | Insane: surface temperature context (null if not computed) |

### 2.3 `shared/grid_SITE.json` (owner: Baldwin), local area around a site

```json
{
  "site": "site_a",
  "window_start": "2027-02-01T00:00Z",
  "step_h": 1,
  "n_steps": 336,
  "rows": 64,
  "cols": 64,
  "cell_size_m": 40,
  "center": {"lat": -89.45, "lon": 137.3},
  "orientation_note": "Rows run top to bottom and columns left to right, matching the south-polar map image; 0° longitude points up.",
  "elevation_m": [[1850.2, 1851.0], [1849.7, 1852.3]],
  "slope_deg": [[3.1, 4.0], [2.2, 18.5]],
  "sun_pct": [[[100, 0], [100, 100]], [[0, 0], [100, 100]]]
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `n_steps` | int | Number of time steps (336 = 14 days at 1 hour) |
| `elevation_m[row][col]` | number | Terrain height per cell |
| `slope_deg[row][col]` | number | Steepest slope in the cell |
| `sun_pct[step][row][col]` | int 0–100 | Percent of the Sun's disk visible from that cell at that step |

### 2.4 `shared/windows_SITE.json` (owner: Baldwin, Pro tier)

Every possible landing time across the year, scored for the mission length in `criteria.json`.

```json
{
  "site": "site_a",
  "mission_days": 10,
  "step_h": 6,
  "rows": [
    {
      "landing": "2027-01-01T00:00Z",
      "usable_days": 7.5,
      "sun_hours": 190,
      "contact_hours": 150,
      "both_hours": 120,
      "longest_dark_h": 18,
      "survives": true
    }
  ]
}
```

### 2.5 `shared/scores.json` (owner: Baldwin)

```json
{
  "generated": "2026-11-15T03:00Z",
  "window_start": "2027-02-01",
  "window_end": "2027-02-28",
  "sites": [
    {
      "site": "site_a",
      "rank": 1,
      "usable_days": 9.5,
      "sun_hours": 520,
      "contact_hours": 300,
      "both_hours": 260,
      "longest_dark_h": 30,
      "survives": true,
      "best_landing": "2027-02-12T06:00Z",
      "brief": "Plain-English summary written by the AI from these numbers only."
    }
  ]
}
```

### 2.6 `shared/rover.json` (owner: Dhiran)

```json
{
  "name": "Sunchaser reference rover",
  "mass_kg": 120,
  "panel": {"area_m2": 0.6, "efficiency": 0.30, "mount": "vertical_sun_tracking"},
  "battery": {"capacity_wh": 2000, "min_soc": 0.15, "charge_efficiency": 0.95},
  "power_w": {"avionics": 30, "comms_active": 25, "heater_dark": 60, "heater_lit": 0},
  "drive": {
    "speed_m_per_h": 200,
    "base_drive_w": 40,
    "rolling_resistance": 0.15,
    "drivetrain_efficiency": 0.5,
    "max_slope_deg": 15
  },
  "comms": {"dte_rate_kbps": 100},
  "uncertainty_pct": {"battery_capacity": 10, "panel_output": 10, "power_draw": 10},
  "sources": "web/SOURCES.md"
}
```

Peak panel power = 1,361 W/m² × `area_m2` × `efficiency` (with placeholders: about 245 W). All numbers are placeholders until Dhiran replaces them with sourced values.

### 2.7 `shared/criteria.json` (owner: Dhiran)

```json
{
  "mission_length_days": 10,
  "usable_day": {"min_sun_hours": 12, "min_contact_hours": 4},
  "max_dark_spell_hours": 18,
  "min_battery_reserve_pct": 15,
  "min_survival_probability": 0.95
}
```

A **usable day** is a 24-hour period with at least `min_sun_hours` of sunlight (`sun_frac` ≥ 0.5) and at least `min_contact_hours` with Earth visible.

### 2.8 `shared/route_SITE.json` (owner: Harril)

```json
{
  "site": "site_a",
  "start": {"row": 6, "col": 6},
  "target": {"row": 55, "col": 50},
  "depart_step": 0,
  "monte_carlo_runs": 500,
  "routes": [
    {
      "name": "shortest",
      "label": "Shortest path",
      "survived": false,
      "frozen_at_index": 37,
      "distance_m": 2650,
      "duration_h": 14.0,
      "energy_used_wh": 1980,
      "min_battery_pct": 0,
      "survival_probability": 0.04,
      "steps": [
        {"t_h": 0.0, "row": 6, "col": 6, "action": "start", "sun_pct": 100,
         "power_in_w": 240, "power_out_w": 70, "battery_wh": 2000}
      ]
    },
    {"name": "sunchaser_fast", "label": "Sunchaser (fastest safe)", "survived": true, "frozen_at_index": null,
     "distance_m": 3100, "duration_h": 22.0, "energy_used_wh": 1500, "min_battery_pct": 21,
     "survival_probability": 0.93, "steps": []},
    {"name": "sunchaser_safe", "label": "Sunchaser (max margin)", "survived": true, "frozen_at_index": null,
     "distance_m": 3400, "duration_h": 27.0, "energy_used_wh": 1400, "min_battery_pct": 48,
     "survival_probability": 0.995, "steps": []}
  ],
  "pareto": [
    {"reserve_pct": 15, "duration_h": 22.0, "survival_probability": 0.93},
    {"reserve_pct": 30, "duration_h": 24.5, "survival_probability": 0.98},
    {"reserve_pct": 45, "duration_h": 27.0, "survival_probability": 0.995}
  ]
}
```

- `action` is `start`, `move` or `wait`. `t_h` is hours since `depart_step`.
- `frozen_at_index` is the index in `steps` where the battery reached zero, or `null`.
- Core ships `shortest` and one Sunchaser route; `sunchaser_safe` and `pareto` are Insane tier (omit if not built).

### 2.9 `api/copilot` (owner: Baldwin, Pro tier)

A serverless function deployed with the website.

- **Request:** `POST /api/copilot` with JSON `{"question": "Which site gives the most usable days in March?", "site": "site_a"}` (`site` optional).
- **Response:** `{"answer": "…", "facts_used": [{"label": "site_b usable days, March", "value": "11.5"}]}`.
- The model calls tools that read the shared JSON; it never invents numbers. The API key lives in a Vercel environment variable, never in the website code.

### 2.10 Repo layout

```
sunchaser/
  PROJECT.md      shared brief (Baldwin)
  README.md       project README (everyone writes their section)
  shared/         all shared JSON (one owner per file)
  data/           Baldwin: data pipeline (Python)
  api/            Baldwin: copilot serverless function
  planner/        Harril: energy model and planners (Python)
  hardware/       Harril: Arduino rover
  web/            Dhiran: web app (React + Vite)
```

---

## 3. GitHub Desktop workflow

Baldwin created the repo and branches. You:

**Once, before Saturday**

1. Accept the collaborator invite from your email.
2. GitHub Desktop: **File → Clone repository** → `sunchaser` → choose a folder → **Clone**. You get the whole repo with every branch.
3. **Current Branch** (top bar) → `planner-(Harril)`. If it's under "Other branches" as `origin/planner-(Harril)`, click it and GitHub Desktop sets it up.
4. Always check the top bar shows `planner-(Harril)` before you commit.

**Every time something works**

1. Changed files appear in **Changes**.
2. Bottom left: a short message ("Add battery sim"), then **Commit to planner-(Harril)**.
3. **Push origin**.

Commit small and often: it's the undo button when the AI breaks something.

**At each checkpoint (Sat 12:00, Sat 18:00, Sun 10:00)**

1. **Branch → Create Pull Request** (opens the browser).
2. **base: main ← compare: planner-(Harril)** → **Create pull request**. Baldwin merges in order: `data-(Baldwin)` → `planner-(Harril)` → `web-(Dhiran)`.

**After the merge: get everyone else's work**

1. **Fetch origin**.
2. **Branch → Update from main** (or **Branch → Merge into current branch…** → `main` → **Merge**).
3. **Push origin**.

**Conflicts:** GitHub Desktop lists the files. **Open in editor**, keep the right lines, delete `<<<<<<<`, `=======`, `>>>>>>>`, save, **Continue merge**. Staying in your own folders makes this rare.

If you accidentally worked on `main`, switch to `planner-(Harril)` and choose to bring your changes with you.

---

## 4. Rules, AI use and honesty

- **Write project code during the event (Nov 14–15).** Several teams say the rules require it, so check the official rules page. Before then: research, learn, practise in throwaway files.
- **Paste this file into your AI at the start of each session.** For each task, also paste the relevant schema from Section 2.
- **Make the AI explain** every function before you move on.
- **Check against reality** with tiny hand-made cases.
- **The README states how we used AI.** It's professional, and judges respect it.
- **Never fake a result.** If something doesn't work, show what does and say what's next.

---

## 5. Your mission (Harril)

You own the part of Sunchaser that feels like real robotics: **a physically grounded rover energy model, a planner that keeps the rover alive as shadows move, a measured survival probability, and (stretch) a real rover on the demo table.** The demo's key moment is yours: the shortest route freezes, the Sunchaser route survives.

**You read:** `shared/rover.json` (Dhiran), `shared/grid_SITE.json` (Baldwin), `shared/timeline_SITE.json` (Baldwin, optional for comms).
**You write:** `shared/route_SITE.json` (schema 2.8), code in `planner/` and `hardware/`.

### 5.1 Your tiers

| Tier | You ship |
| --- | --- |
| **Core** | Energy model (solar in, avionics, heaters, flat driving), battery simulator, 2D A\* shortest route, one space-time Sunchaser route, `route_SITE.json` for one site |
| **Pro** | Drive power from slope and rolling resistance, partial-sun input, Monte Carlo survival probability, routes for every site |
| **Insane** | Fast-vs-safe Pareto routes, mid-route replanning demo, hardware-in-the-loop Arduino rover with a light sensor |

**Decision points:** if Core isn't working by **Sat 22:00**, drop the space-time planner for the "park and wait" fallback (5.7). Only start hardware after Pro is committed.

### 5.2 Code layout (Python 3.11+, `numpy` allowed, nothing exotic)

```
planner/
  sunchaser/
    __init__.py
    io.py           load rover.json, grid, timeline; save route json
    physics.py      power in, power out, drive power, battery step
    sim.py          simulate a route step by step
    astar2d.py      shortest route on the grid (ignores sunlight)
    astar_st.py     space-time sun-chasing planner
    montecarlo.py   survival probability
    pareto.py       fast-vs-safe routes (Insane)
    replan.py       replanning demo (Insane)
  fake/
    make_fake.py    generates grid_fake.json and rover_fake.json
  tests/
    test_physics.py
    test_astar.py
  run.py            plan all routes for every site and write shared/route_SITE.json
  README_planner.md how it works, in plain English
hardware/
  rover/rover.ino   Arduino sketch
  bridge.py         laptop ↔ rover link (serial)
```

Run with `python planner/run.py --site site_a` (and `--all`).

### 5.3 Step 1: fake data (Sat 09:00–10:00)

Build a fake world that already behaves like the south pole, so your planner has something real to beat:

- **Grid:** 40 × 40 cells, 40 m each, 72 hourly steps.
- **Terrain:** a flat plain at 1,800 m plus three Gaussian hills (100–250 m tall, 300–600 m wide) and one steep ridge (slope above 15°) with a gap.
- **Sun:** elevation 1.0°, azimuth rotating 0.5° per hour (one full circle per lunar day is about 0.51° per hour).
- **Shadows:** for each cell and hour, march toward the Sun's azimuth; the cell is shaded if any terrain ahead rises above the Sun's elevation. Set `sun_pct` to 100 or 0 for Core (or partial for Pro).
- **Rover:** copy the `rover.json` example from Section 2.6.

Save in the exact schemas (2.3 and 2.6) as `planner/fake/grid_fake.json` and `planner/fake/rover_fake.json`.

> **AI prompt:** "Using the brief and Section 2.3 of this handbook, write planner/fake/make_fake.py. 40×40 grid, 40 m cells, 72 hourly steps, base elevation 1800 m, three Gaussian hills (heights 100–250 m, widths 300–600 m), one ridge with slope over 15° and a gap. Sun elevation 1.0°, azimuth starting at 0° and rotating 0.5° per hour. A cell is shaded at an hour if, marching from the cell toward the Sun's azimuth in half-cell steps up to 2 km, any terrain rises above the line at the Sun's elevation. Compute slope_deg from elevation with central differences. Output grid_fake.json exactly in schema 2.3, with sun_pct 0 or 100. Explain the shadow test."

### 5.4 Step 2: the physics (Sat 10:00–12:00)

Put every equation in `physics.py`, each as a small function with a docstring.

**Power in (solar):**

```
panel_peak_w = 1361 × panel.area_m2 × panel.efficiency
power_in_w   = panel_peak_w × (sun_pct / 100)
```

The panel is vertical and sun-tracking, and the Sun is within about 1.5° of the horizon, so the angle loss (cos of elevation) is negligible. Say this in a comment.

**Power out:**

```
heater_w = power_w.heater_dark if sun_pct < 5 else power_w.heater_lit
power_out_w = power_w.avionics + heater_w (+ drive_w if moving) (+ comms_active if transmitting, Pro)
```

**Drive power (Core: flat; Pro: slope and regolith):**

```
v = speed_m_per_h / 3600                                   # metres per second
theta = atan((elev_next - elev_here) / horizontal_distance) # slope along the direction of travel
mech_w = mass_kg × 1.62 × v × (rolling_resistance × cos(theta) + sin(theta))
drive_w = base_drive_w + max(0, mech_w) / drivetrain_efficiency   # no energy recovered downhill
```

Core uses `theta = 0`.

**Battery step over `dt` hours:**

```
net = power_in_w - power_out_w
if net > 0: energy += net × charge_efficiency × dt
else:       energy += net × dt
energy = min(energy, capacity_wh)
frozen  = energy <= 0
reserve_breached = energy < min_soc × capacity_wh
```

**Hand-check numbers (put these in `tests/test_physics.py`):**

| Case | Expected |
| --- | --- |
| Panel peak with placeholders | 1361 × 0.6 × 0.30 ≈ 245 W |
| Parked in the dark: out = 30 + 60 | 90 W, so 2,000 Wh lasts about 22.2 h to empty, 18.9 h to the 15% reserve |
| Parked in full sun: net = 245 − 30 = 215 W × 0.95 | ≈ 204 Wh gained per hour, capped at 2,000 Wh |
| Flat drive mechanical power, 120 kg at 200 m/h | 120 × 1.62 × 0.0556 × 0.15 ÷ 0.5 ≈ 3.2 W |
| 15° uphill mechanical power | 120 × 1.62 × 0.0556 × (0.15 cos 15° + sin 15°) ÷ 0.5 ≈ 8.7 W |

That last pair is a great interview insight: **on the Moon at walking pace, heaters and electronics dominate energy use; slope barely matters.** So the planner's real job is to avoid darkness, not hills (beyond the slope limit for safety).

> **AI prompt:** "Using the brief and schema 2.6, write planner/sunchaser/physics.py with functions panel_peak_w(rover), power_in_w(rover, sun_pct), heater_w(rover, sun_pct), drive_w(rover, elev_here, elev_next, horizontal_m), and battery_step(rover, energy_wh, power_in_w, power_out_w, dt_h) returning (new_energy, frozen, reserve_breached). Use exactly these equations: [paste 5.4]. Then write tests/test_physics.py checking every row of the hand-check table to within 1%. Explain each function."

### 5.5 Step 3: simulator (Sat 10:00–12:00, with physics)

`sim.py` takes a planned path and replays it through time:

- Input: `rover`, `grid`, `depart_step`, and a list of steps `(action, row, col, duration_h)`.
- Moves take `distance ÷ speed` hours: side neighbour `cell_size_m`, diagonal `cell_size_m × √2`. Simulate each move in sub-steps of at most 0.25 h, using the `sun_pct` of the cell the rover is in at `floor(depart_step + t)`.
- Output: every step with `t_h`, `sun_pct`, `power_in_w`, `power_out_w`, `battery_wh`, plus `survived`, `frozen_at_index`, `energy_used_wh`, `min_battery_pct`, `distance_m`, `duration_h`.
- If the time runs past the grid's `n_steps`, stop and mark the route "out of time window".

### 5.6 Step 4: shortest route, 2D A\* (Sat 12:00–15:00)

The route a naive planner picks: shortest distance, ignoring the Sun.

- 8-connected grid. A move is **blocked** if either cell's `slope_deg` exceeds `max_slope_deg`, or the slope along the move exceeds it.
- Cost: distance in metres. Heuristic: octile distance (exact for 8-connected grids with no obstacles), which never overestimates.
- Tie-breaking: prefer the larger g-value to reduce explored nodes.

```
open = heap of (f, g, cell) starting with (h(start), 0, start)
best_g = {start: 0}; came_from = {}
while open:
    f, g, cell = pop(open)
    if cell == target: return rebuild(came_from, cell)
    if g > best_g[cell]: continue
    for nb, step_cost in neighbours(cell):
        if blocked(cell, nb): continue
        ng = g + step_cost
        if ng < best_g.get(nb, inf):
            best_g[nb] = ng; came_from[nb] = cell
            push(open, (ng + h(nb), ng, nb))
return None
```

Then simulate it from `depart_step`. On a good scenario it drives straight through shadow and freezes.

> **AI prompt:** "Write planner/sunchaser/astar2d.py: 8-connected A* on grid_SITE.json using octile-distance heuristic, cost in metres (side = cell_size_m, diagonal = cell_size_m·√2), blocked when either cell's slope_deg or the slope along the move exceeds max_slope_deg from rover.json. Return the list of (row, col). Add tests in tests/test_astar.py: an open 5×5 grid gives a straight diagonal; a wall with one gap forces the path through the gap. Explain why octile distance is admissible."

### 5.7 Step 5: the Sunchaser planner, space-time A\* (Sat 15:00–24:00)

The heart of the project. The rover may **move or wait**, and the planner tracks **time** and **energy**, so it learns to park in sunlight while a shadow passes.

**State:** `(row, col, t_h, energy_wh)`.

**Actions from each state:**

- **Move** to one of 8 neighbours (if not blocked). Duration = distance ÷ speed. Energy updated by simulating that move with the physics (sub-steps as in 5.5).
- **Wait** 1 hour (Pro: also 0.5 h). Energy updated with parked power (avionics + heater if dark) and solar input.

**Constraints:**

- Discard the action if energy would fall below the reserve: `min_soc × capacity_wh` (this is what makes the route *safe*, not just alive).
- Discard if time runs past the grid's window.

**Goal and cost:** reach the target; minimise arrival time (`g = t_h`).

**Heuristic:** octile distance to the target ÷ speed (the fastest conceivable arrival). Admissible because waiting and detours only add time.

**Keeping the search fast (important on a 64×64×336 world):**

1. **Dominance pruning (the professional way).** Keep, for every cell, a list of non-dominated labels `(t_h, energy_wh)`. A new state is **dominated** if some existing label at the same cell arrived no later *and* with at least as much energy. Skip dominated states. This is the standard technique for resource-constrained shortest paths.
2. **Simpler alternative if short on time:** a visited set keyed by `(row, col, floor(t_h), round(energy / 50))`.
3. Wait only where it can matter: allow `wait` when the current cell's `sun_pct` is going to change within the next few hours, or when it's lit and the battery isn't full.

```
start = (sr, sc, 0.0, capacity_wh)
open = heap of (t + h, t, state)
labels = {cell: [(t, e)]}
while open:
    take the state with the lowest f
    if cell == target: return rebuild(state)
    for action in moves_and_wait(state):
        new = apply(action)              # physics update
        if new.energy < reserve or new.t > window_end: continue
        if dominated(labels[new.cell], new): continue
        add_label(labels[new.cell], new); remember parent; push
return None                              # no safe route exists in this window
```

**Tests:**

- On a fully lit grid, the Sunchaser route equals the shortest route (no reason to wait).
- On the fake world with a shadow sweeping across the straight line, the shortest route freezes and the Sunchaser route survives by waiting or detouring.
- No route ever passes through a blocked cell or drops below the reserve.

> **AI prompt:** "Using the brief, schemas 2.3/2.6/2.8 and my physics.py and sim.py, write planner/sunchaser/astar_st.py: a resource-constrained space-time A* where each state is (row, col, t_h, energy_wh). Actions: 8 moves (duration = distance/speed, energy via physics with ≤0.25 h sub-steps using sun_pct at floor(depart_step + t)) and wait 1 h. Discard states below min_soc reserve or past the grid's window. Minimise arrival time; heuristic = octile distance / speed. Use per-cell Pareto labels (t, energy) for dominance pruning. Return steps in schema 2.8 format. Then explain dominance pruning to me with a tiny example."

**Fallback if this isn't working by Sat 22:00: "park and wait".** Along the shortest route, find where the battery would breach the reserve; before that point, find the nearest reachable cell with the most sun over the coming hours; drive there, wait until the shadow ahead clears (or the battery is full), continue with 2D A\*. Simulate it. It tells the same story with simpler code.

### 5.8 Step 6: Monte Carlo survival probability (Pro, Sun 08:00–10:00)

Real hardware never matches its spec sheet. Instead of saying "survives", say **"survives in 97% of 500 simulated missions"**.

For each route, run the simulator `N = 500` times. Each run multiplies:

- battery capacity by a random factor from a normal distribution with mean 1 and standard deviation `uncertainty_pct.battery_capacity / 100`,
- panel output by `normal(1, uncertainty_pct.panel_output / 100)`,
- all power draws by `normal(1, uncertainty_pct.power_draw / 100)`,

clipped to 0.5–1.5, plus a random departure delay of 0–2 hours. `survival_probability` = fraction of runs that never freeze. Fix the random seed so results are reproducible. Use numpy to keep it fast.

> **AI prompt:** "Write planner/sunchaser/montecarlo.py: survival_probability(route_steps, rover, grid, depart_step, n=500, seed=42) that re-simulates the route with capacity, panel output and power draws each scaled by normal(1, σ) from rover.json uncertainty_pct (clipped 0.5–1.5) and a uniform 0–2 h departure delay; returns the fraction of runs that never reach zero energy, and the 5th-percentile minimum battery. Explain why we fix the seed."

### 5.9 Step 7: fast vs safe (Insane, Sun 10:00–12:00)

There's a real trade-off: arriving fast with a thin battery margin, or slower with a fat one. Show it.

Re-run the space-time planner with the reserve set to 15%, 30% and 45% of capacity. Each gives a route; compute its duration and survival probability. Save:

- `sunchaser_fast` = the 15% route, `sunchaser_safe` = the highest-reserve route that still reaches the target,
- the `pareto` list (schema 2.8) for Dhiran to chart as "time vs survival probability".

**Replanning demo (Insane, optional):** halfway along `sunchaser_fast`, inject an event ("dust on the panels: output −30%"), replan from the current state, and save both versions. It shows an autonomous rover adapting.

### 5.10 Step 8: `run.py` and outputs

For each site with a grid:

1. Load `shared/rover.json` and `shared/grid_SITE.json`.
2. Choose start and target automatically: gentle, lit cells near opposite corners at `depart_step`, at least 2 km apart (allow overrides via command-line flags).
3. Plan `shortest`, `sunchaser_fast` (and `sunchaser_safe`, `pareto` if built), simulate each, run Monte Carlo.
4. Write `shared/route_SITE.json` exactly per schema 2.8.
5. Print one line per route, e.g. `shortest: FROZE at 9.3 h (p_survive 0.04) | sunchaser_fast: 22.0 h, min battery 21%, p_survive 0.93`.

**Find a dramatic scenario:** if both routes survive everywhere, the scenario is too easy. Try other departure steps or targets (loop over `depart_step` and keep the one where shortest freezes and Sunchaser survives). Tell Baldwin and Dhiran which site and time make the best demo.

### 5.11 Self-checks before every merge

- [ ] No step passes through a blocked cell.
- [ ] Every `move` goes to a neighbouring cell; `t_h` always increases.
- [ ] Battery never exceeds capacity; Sunchaser routes never drop below the reserve.
- [ ] `survival_probability` is between 0 and 1, and higher for the safer route.
- [ ] JSON validates against schema 2.8 (write a tiny check function).
- [ ] All tests pass.

---

## 6. Hardware-in-the-loop rover (Insane, only after Pro is committed)

A real robot on the table whose **light sensor drives the battery simulation live**. Shine a desk lamp ("the Sun"), the rover charges on screen; cast a shadow over it, the battery drains; let it run too low and the laptop commands it to stop and wait. Judges and employers remember this.

**Parts (a cheap starter kit; prices vary):** Arduino Uno (or compatible), 2WD robot car chassis with motors, L298N motor driver, battery pack for motors, light-dependent resistor (LDR) + 10 kΩ resistor, USB cable (or an HC-05 Bluetooth module for wireless).

**Wiring:**

- LDR and 10 kΩ resistor as a voltage divider into analog pin A0.
- L298N: IN1–IN4 to digital pins (e.g. 5, 6, 9, 10), ENA/ENB to PWM pins, motor power from the battery pack, common ground with the Arduino.

**How it works:**

1. `bridge.py` (on the laptop) loads the Sunchaser route, converts it to commands (`F n` forward n cells, `L 45`/`R 45` turn, `W s` wait seconds) using the rover's start heading, and sends them over serial.
2. The Arduino executes commands and streams `LIGHT <0–1023>` readings ten times a second.
3. `bridge.py` maps light to `sun_pct` (calibrate: lamp on = 100, covered = 0), runs `physics.battery_step` in compressed time (e.g. 1 real second = 1 simulated hour), prints and plots the battery live, and sends `STOP` if it would breach the reserve, then `GO` once recharged.

**Calibration:** measure milliseconds per cell forward and per 45° turn on the actual floor or printed map; put them as constants at the top of the sketch.

**Demo:** print the grid big (A2 or tiled A4) with the shadow shaded, film the rover following the Sunchaser route next to the screen animation.

> **AI prompt:** "Write hardware/rover/rover.ino for an Arduino Uno with an L298N (IN1–IN4 on pins 5, 6, 9, 10; ENA 3, ENB 11) and an LDR divider on A0. It reads newline-terminated serial commands F n, L deg, R deg, W s, STOP, GO; executes them using MS_PER_CELL and MS_PER_45_DEG constants; and prints LIGHT <value> ten times per second. Then write hardware/bridge.py that converts a schema-2.8 route into those commands, streams them, reads LIGHT values, maps them to sun_pct with two calibration constants, runs my physics.battery_step at 1 s = 1 h, plots battery live with matplotlib, and sends STOP below the reserve and GO when recharged."

---

## 7. Prep before the event (learning only, no project code)

- [ ] Accept the GitHub invite, clone, switch to `planner-(Harril)`, practise one commit and push with a throwaway file.
- [ ] Read the full challenge statement (Section 1.1).
- [ ] Do one A\* tutorial on a 2D grid in Python.
- [ ] Have your AI teach you **resource-constrained shortest paths** and **dominance pruning** with a tiny example until you can explain it back.
- [ ] Learn the basics of Monte Carlo simulation (one short video or tutorial).
- [ ] Agree rover numbers with Dhiran (he owns `rover.json`).
- [ ] If doing hardware: buy the parts this week; practise driving straight and turning 45° in a throwaway sketch.

---

## 8. Weekend schedule

| When | Goal |
| --- | --- |
| Sat 09:00–10:00 | Team agrees schemas; you generate the fake world |
| Sat 10:00–12:00 | Physics + simulator + tests passing |
| **Sat 12:00** | **Checkpoint:** pull request |
| Sat 12:00–15:00 | 2D A\* shortest route; first `route_SITE.json` on fake data |
| Sat 15:00–18:00 | Space-time A\* first version |
| **Sat 18:00** | **Checkpoint:** pull request; update from main to get real `grid_SITE.json` |
| Sat 18:00–22:00 | Space-time A\* on real data with dominance pruning |
| **Sat 22:00** | **Decision:** keep space-time A\* or switch to park-and-wait |
| Sat 22:00–02:00 | Slope-aware drive power; dramatic scenario search. Then sleep. |
| Sun 08:00–10:00 | Monte Carlo survival probability |
| **Sun 10:00** | **Checkpoint:** real routes for every site in `shared/` |
| Sun 10:00–13:00 | Insane tier: Pareto routes, replanning, or hardware |
| **Sun 13:00** | **Feature freeze.** Write `README_planner.md` and your README section; help film the demo |

---

## 9. Your part of the demo and README

**Demo (about 20 seconds of the 60-second video):** two routes side by side on the map. The shortest route drives into shadow; its battery bar drains; it freezes. The Sunchaser route waits on a sunlit ridge, then drives on and arrives. Caption: "Sunchaser: 97% survival. Shortest path: 4%." Then the real rover clip, if built.

**Your README section (plain English):**

- The rover model and where its numbers come from.
- The energy insight: heaters and electronics dominate; darkness, not slope, is the enemy.
- How the planner works: space-time A\*, waiting in sunlight, the safety reserve, dominance pruning.
- Monte Carlo: what uncertainty you modelled and why survival is a probability.
- Headline result, e.g. "At site A on Feb 12, the shortest route froze after 9.3 h; Sunchaser arrived in 22 h with a 97% survival probability."
- What's simplified (no wheel slip, simplified thermal model) and what's next.

---

## 10. Done means

- [ ] `shared/route_SITE.json` for every site, matching schema 2.8 exactly.
- [ ] Shortest route freezes and Sunchaser survives on at least one dramatic scenario.
- [ ] Survival probabilities computed (Pro).
- [ ] All self-checks (5.11) and tests pass.
- [ ] `README_planner.md` and your README section written.
- [ ] Everything committed, pull request merged into main.

## Interview questions you must be able to answer

1. Why does the shortest route fail at the lunar south pole?
2. Walk me through your energy model. Why do heaters matter more than hills?
3. How does A\* work, and why must the heuristic never overestimate?
4. Why did you add time and energy to the search state? What is dominance pruning and why does it keep the search tractable?
5. Why report survival as a probability? What did you randomise?
6. What's the trade-off between the fast and the safe route, and how would a mission team choose?
7. What would you change to fly this on a real rover?
