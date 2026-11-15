# Sunchaser: Project Brief (CLAUDE.md / PROJECT.md)

**Team Zenon · NASA Space Apps Challenge 2026 · November 14–15, 2026**

> This file is the single source of truth for the project. Claude Code loads it automatically when it sits in the repo root as `CLAUDE.md`. Teammates using other AI tools paste it in at the start of each session. Each person also has a personal handbook (`plan-robotics.md`, `plan-engineering-business.md`, `HANDOFF-baldwin.md`) with their detailed build guide.

---

## 0. Brief for any AI assistant working in this repo

You are helping Team Zenon build **Sunchaser** during the 48-hour NASA Space Apps Challenge 2026. The official challenge is **"Lunar Landing Site Navigator"** (formerly "CLPS Lunar Mission Browser"): build an easy tool to compare lunar south-pole landing sites and dates, showing when the Sun and Earth are above the local horizon, so planners can judge solar power and direct-to-Earth communication windows.

Sunchaser goes far beyond that minimum: terrain-aware sunlight and Earth visibility from JPL Horizons and LRO LOLA; a year-long landing-window scan; a first-principles rover energy model; sun-chasing space-time A* routes with Monte Carlo survival probability; a business case (cost per usable mission day, cost of a launch slip); a grounded AI mission copilot; and a polished web app with map, timelines, heatmap, 2D/3D rover playback and dashboard.

**Team and ownership (strict):**

| Person | Role | Branch | Writes only in |
| --- | --- | --- | --- |
| Baldwin | Data, AI and tech lead | `data-(Baldwin)` | `data/`, `api/`, `CLAUDE.md`/`PROJECT.md`, and the shared files he owns |
| Harril | Robotics lead | `planner-(Harril)` | `planner/`, `hardware/`, and `shared/route_*.json` |
| Dhiran | Engineering and business lead | `web-(Dhiran)` | `web/`, `shared/rover.json`, `shared/criteria.json` |

**Rules for the AI (follow every one):**

1. **Only write code in the current person's folders.** Never edit another person's folder; draft a message to its owner instead. Ask which person you're working for if unclear.
2. **Shared JSON files must match Section 2 exactly:** names, types, units, orders. Never change a schema silently.
3. **Real physics, real NASA data.** Never present an invented number as a fact; label estimates.
4. **Build in tiers: Core → Pro → Insane.** Don't start a higher tier until the lower one works end to end, is tested and committed.
5. **Readable, commented code, explained in plain language.** Every teammate must be able to explain their part in a job interview.
6. **Test with hand-checkable cases** before real data.
7. **Conventions:** ISO 8601 UTC times ending in `Z`; degrees; metres; watts (W); watt-hours (Wh); percentages 0–100 unless a field says fraction (0–1).
8. **Performance:** website data files a few MB per site at most; Python runs finish in minutes.
9. **Be honest about limits** in every output that simplifies reality.

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

Baldwin created the repo and branches. Each teammate:

**Once, before Saturday**

1. Accept the collaborator invite from your email.
2. GitHub Desktop: **File → Clone repository** → `sunchaser` → choose a folder → **Clone**. You get the whole repo with every branch.
3. **Current Branch** (top bar) → `YOUR-BRANCH`. If it's under "Other branches" as `origin/YOUR-BRANCH`, click it and GitHub Desktop sets it up.
4. Always check the top bar shows `YOUR-BRANCH` before you commit.

**Every time something works**

1. Changed files appear in **Changes**.
2. Bottom left: a short message ("Add battery sim"), then **Commit to YOUR-BRANCH**.
3. **Push origin**.

Commit small and often: it's the undo button when the AI breaks something.

**At each checkpoint (Sat 12:00, Sat 18:00, Sun 10:00)**

1. **Branch → Create Pull Request** (opens the browser).
2. **base: main ← compare: YOUR-BRANCH** → **Create pull request**. Baldwin merges in order: `data-(Baldwin)` → `planner-(Harril)` → `web-(Dhiran)`.

**After the merge: get everyone else's work**

1. **Fetch origin**.
2. **Branch → Update from main** (or **Branch → Merge into current branch…** → `main` → **Merge**).
3. **Push origin**.

**Conflicts:** GitHub Desktop lists the files. **Open in editor**, keep the right lines, delete `<<<<<<<`, `=======`, `>>>>>>>`, save, **Continue merge**. Staying in your own folders makes this rare.

If you accidentally worked on `main`, switch to `YOUR-BRANCH` and choose to bring your changes with you.

---

## 4. Rules, AI use and honesty

- **Write project code during the event (Nov 14–15).** Several teams say the rules require it, so check the official rules page. Before then: research, learn, practise in throwaway files.
- **Paste this file into your AI at the start of each session.** For each task, also paste the relevant schema from Section 2.
- **Make the AI explain** every function before you move on.
- **Check against reality** with tiny hand-made cases.
- **The README states how we used AI.** It's professional, and judges respect it.
- **Never fake a result.** If something doesn't work, show what does and say what's next.
