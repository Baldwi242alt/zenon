# Sunchaser: Engineering & Business Lead Handbook

**Team Zenon · NASA Space Apps Challenge 2026 · November 14–15, 2026**
**Owner:** Dhiran (engineering and business lead) · **Branch:** `web-(Dhiran)` · **You write in:** `web/`, `shared/rover.json`, `shared/criteria.json`

> **How to use this file:** paste this entire file into your AI assistant at the start of every session, then tell it what you're working on. It's written so the AI knows the full project, the exact data formats, what you own, and how good the result has to be. If you finish everything here, you've built one third of Sunchaser.

---

## 0. Brief for the AI assistant

You are helping **Dhiran**, the **engineering and business lead** on Team Zenon, a three-person team building **Sunchaser** during the 48-hour NASA Space Apps Challenge 2026 (November 14–15, 2026). The official challenge is **"Lunar Landing Site Navigator"** (formerly "CLPS Lunar Mission Browser"): build an easy tool to compare lunar south-pole landing sites and dates, showing when the Sun and Earth are above the local horizon, so planners can judge solar power and direct-to-Earth communication windows.

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

1. **Only write code in Dhiran's folders.** Never edit another person's folder. If something there needs to change, write a short message Dhiran can send to its owner.
2. **The shared JSON files must match Section 2 exactly:** field names, types, units, array orders. If you believe a schema should change, say so explicitly; never change it silently.
3. **Real physics, real NASA data.** Never present an invented number as a fact. Anything estimated is labelled "estimate" in code comments and in the output.
4. **Build in tiers: Core → Pro → Insane.** Do not start a higher tier until the lower tier works end to end, is tested, and is committed. A finished Core beats a half-built Insane.
5. **Readable, commented code.** After writing a function, explain it to Dhiran in plain language. Dhiran must be able to explain every part in a job interview.
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
3. **Current Branch** (top bar) → `web-(Dhiran)`. If it's under "Other branches" as `origin/web-(Dhiran)`, click it and GitHub Desktop sets it up.
4. Always check the top bar shows `web-(Dhiran)` before you commit.

**Every time something works**

1. Changed files appear in **Changes**.
2. Bottom left: a short message ("Add battery sim"), then **Commit to web-(Dhiran)**.
3. **Push origin**.

Commit small and often: it's the undo button when the AI breaks something.

**At each checkpoint (Sat 12:00, Sat 18:00, Sun 10:00)**

1. **Branch → Create Pull Request** (opens the browser).
2. **base: main ← compare: web-(Dhiran)** → **Create pull request**. Baldwin merges in order: `data-(Baldwin)` → `planner-(Harril)` → `web-(Dhiran)`.

**After the merge: get everyone else's work**

1. **Fetch origin**.
2. **Branch → Update from main** (or **Branch → Merge into current branch…** → `main` → **Merge**).
3. **Push origin**.

**Conflicts:** GitHub Desktop lists the files. **Open in editor**, keep the right lines, delete `<<<<<<<`, `=======`, `>>>>>>>`, save, **Continue merge**. Staying in your own folders makes this rare.

If you accidentally worked on `main`, switch to `web-(Dhiran)` and choose to bring your changes with you.

---

## 4. Rules, AI use and honesty

- **Write project code during the event (Nov 14–15).** Several teams say the rules require it, so check the official rules page. Before then: research, learn, practise in throwaway files.
- **Paste this file into your AI at the start of each session.** For each task, also paste the relevant schema from Section 2.
- **Make the AI explain** every function before you move on.
- **Check against reality** with tiny hand-made cases.
- **The README states how we used AI.** It's professional, and judges respect it.
- **Never fake a result.** If something doesn't work, show what does and say what's next.

---

## 5. Your mission (Dhiran)

You own three things that decide whether Sunchaser looks like a student project or a real product:

1. **Engineering realism:** the rover's numbers and the rules for what counts as a usable day. Every other result depends on them.
2. **The business story:** who pays, what it's worth, and what a bad decision costs.
3. **The product:** a polished web app that makes the whole team's work understandable in seconds, plus the pitch.

**You write:** `shared/rover.json` (schema 2.6), `shared/criteria.json` (schema 2.7), everything in `web/`.
**You read:** every other file in `shared/` and the `api/copilot` endpoint.

**Your first job on Saturday at 09:00 is handing over `rover.json` and `criteria.json`.** Harril and Baldwin both depend on them, so prepare drafts during the prep weeks.

### 5.1 Your tiers

| Tier | You ship |
| --- | --- |
| **Core** | Sourced `rover.json` and `criteria.json`; web app with Mission Map, Light & Comms timeline, 2D Rover Ops playback, Business dashboard (cost per usable day); deployed on Vercel |
| **Pro** | Landing-window heatmap, site compare mode, cost-of-a-slip chart, survival-probability and Pareto charts, Copilot chat, Methods page |
| **Insane** | 3D terrain with live shadows and the rover driving; sensitivity analysis; cinematic intro |

**Decision points:** Core screens must show real data by **Sun 10:00**. Only start 3D after Pro screens are committed.

### 5.2 Engineering specs: `shared/rover.json`

**Goal:** numbers a lunar engineer would find believable for a small solar-powered south-pole rover, each with a source or a clearly labelled estimate.

**Where to look:** NASA Technical Reports Server (ntrs.nasa.gov), published papers and NASA pages on small lunar rovers (for example NASA's VIPER design, ISRO's Pragyan, China's Yutu rovers, and CLPS rover payloads), and battery and solar-cell datasheets for space-grade parts.

| Field | What it means | How to set it |
| --- | --- | --- |
| `mass_kg` | Rover mass | Published mass of a comparable small rover |
| `panel.area_m2`, `panel.efficiency` | Solar panel size and cell efficiency | Published panel area; space-grade multi-junction cells are roughly 28–32% efficient |
| `panel.mount` | Panel layout | `vertical_sun_tracking` (justify: the Sun is on the horizon) |
| `battery.capacity_wh` | Stored energy | Published battery capacity |
| `battery.min_soc` | Reserve never to be used | 10–20% is a common design margin; justify your choice |
| `battery.charge_efficiency` | Charging losses | Lithium-ion is typically around 0.9–0.97 |
| `power_w.avionics` | Computers, sensors, radio idle | Published standby power |
| `power_w.comms_active` | Extra power while transmitting | Published transmit power |
| `power_w.heater_dark`, `heater_lit` | Survival heating | Published survival heater power |
| `drive.speed_m_per_h` | Average traverse speed (not top speed) | Published traverse rates; small lunar rovers are slow |
| `drive.base_drive_w` | Motor electronics while driving | Estimate from motor specs |
| `drive.rolling_resistance` | Regolith rolling resistance | Terramechanics literature; roughly 0.1–0.3 for loose soil |
| `drive.drivetrain_efficiency` | Motor and gearbox efficiency | Typically 0.4–0.7 |
| `drive.max_slope_deg` | Steepest safe slope | Published slope limit |
| `comms.dte_rate_kbps` | Direct-to-Earth data rate | Published rate for a small lander or rover radio |
| `uncertainty_pct.*` | How far reality may differ | 10% each is a reasonable start; justify it |

The ranges above are starting points for your research, not sources. Every final number goes in `web/SOURCES.md` with its title and link, or the word **estimate** and one line of reasoning.

**Sanity checks before you hand it over (write them in `SOURCES.md`):**

- **Peak solar power** = 1,361 × area × efficiency.
- **Dark endurance** = `capacity_wh × (1 − min_soc) ÷ (avionics + heater_dark)`. With placeholders: 2,000 × 0.85 ÷ 90 ≈ 18.9 hours.
- **Recharge time** from reserve to full = `capacity_wh × (1 − min_soc) ÷ ((peak − avionics) × charge_efficiency)`. Placeholders: 1,700 ÷ 204 ≈ 8.3 hours.
- **Drive power** on flat ground = `base_drive_w + mass × 1.62 × v × rolling_resistance ÷ efficiency` (v in m/s). Placeholders: about 43 W. This shows heaters and electronics dominate, which is a strong point for the pitch.
- **The scenario must be interesting:** dark endurance should be shorter than some shadows at the candidate sites and longer than others. If every shadow is survivable or none are, discuss with Harril and Baldwin and adjust the scenario (site, date, mission profile), never fake the specs.

> **AI prompt:** "I'm setting realistic specs for a small solar-powered rover at the lunar south pole, in exactly this schema: [paste 2.6]. For each field, explain what drives the number, a typical range for small lunar rovers, and what to search for on ntrs.nasa.gov or in published papers to find a real figure. Don't invent citations. Then compute peak solar power, dark endurance, recharge time and flat-ground drive power from my draft numbers: [paste draft]."

### 5.3 Scoring rules: `shared/criteria.json`

| Field | Meaning | How to choose it |
| --- | --- | --- |
| `mission_length_days` | Required mission duration | Small CLPS missions run days to about two weeks; pick one and justify it |
| `usable_day.min_sun_hours` | Sun hours needed in a day for it to count | Enough to recharge what a day costs (use your recharge-time maths) |
| `usable_day.min_contact_hours` | Earth contact needed in a day | Enough to send the day's data at `dte_rate_kbps`; justify it |
| `max_dark_spell_hours` | Longest darkness the rover can survive | Your dark endurance from 5.2 (already includes the reserve) |
| `min_battery_reserve_pct` | Reserve the planner must keep | Same as `min_soc × 100` |
| `min_survival_probability` | Risk tolerance | 0.95 is a sensible default for a commercial mission |

Agree the **usable day** definition with Baldwin on Saturday morning (Section 2.7).

### 5.4 The business model

You'll present this in two slides and one dashboard screen.

1. **Customer:** companies flying landers and rovers under NASA's CLPS program, and the agencies, universities and companies buying payload space on them.
2. **Problem:** at the south pole, a bad site, date or route wastes surface days or kills the rover, and surface days are the most expensive days of the mission.
3. **Solution:** Sunchaser picks the site, landing window and route that maximise usable days and survival, with NASA data behind every number.
4. **Value metrics:**
   - **Cost per usable mission day** = mission budget ÷ usable days. The user enters their own budget, so you never invent prices.
   - **Cost of a launch slip** (Pro): using `windows_SITE.json`, show how usable days, and so cost per usable day, change if landing slips by 1, 2, 3 or 7 days. This is the killer business chart: "a 48-hour slip at site B cuts usable days from 9 to 4, doubling your cost per day."
   - **Science returned** = contact hours × `dte_rate_kbps` (convert to gigabytes). "Site A returns 2.3× more data for the same budget."
5. **Why now:** commercial landers are already reaching the south pole, and planning tools haven't caught up.
6. **Headline:** one comparison from real results. Only use numbers the tool produced.

**Sensitivity (Insane):** a small chart showing how usable days at the top site change if battery capacity or panel output is 20% lower (ask Harril to run those two extra scenarios).

> **AI prompt:** "Help me write a two-slide business case for Sunchaser [paste the pitch from 1.4]. Customer: CLPS lunar delivery companies and their payload customers. Value metrics: cost per usable mission day (budget ÷ usable days), cost of a launch slip, data returned per budget. Five short bullets per slide. No invented market sizes or prices."

### 5.5 The web app: architecture

**Stack:**

- **React + TypeScript + Vite** (TypeScript catches data-shape mistakes early and looks professional).
- **React Router** for screens; a small global store (Zustand, or React context) for the selected site, date range and playback time.
- **Charts:** Recharts for standard charts; plain SVG or canvas for the timeline bands and heatmap (faster with thousands of hours).
- **2D playback:** HTML canvas.
- **3D (Insane):** react-three-fiber + drei (Three.js for React).
- **Deploy:** Vercel.

**Setup (Sat 10:00):**

1. In the repo root: `npm create vite@latest web -- --template react-ts`, then `cd web`, `npm install`, `npm install react-router-dom zustand recharts`.
2. In `web/vite.config.ts` set `publicDir: '../shared'`, so `fetch('/sites.json')` loads `shared/sites.json`. New data appears as soon as you update from main.
3. Put images in `web/src/assets/`.
4. Write TypeScript types for every schema in Section 2 in `web/src/types.ts`. Your AI can generate them from the examples.
5. Deploy to Vercel immediately (5.12), even if the page is blank.

**Structure:**

```
web/src/
  types.ts            types for every shared schema
  data/loaders.ts     fetch + cache each JSON file; loading and "no data yet" states
  store.ts            selected site, date range, playback time
  theme.css           design tokens (colours, spacing, fonts)
  components/         SiteCard, TimelineBands, ElevationChart, Heatmap, RoverCanvas, BatteryBar, StatTile, CopilotPanel
  screens/            MissionMap, LightComms, LandingWindows, RoverOps, Business, Copilot, Methods
  three/              Terrain3D (Insane)
  App.tsx             layout, navigation, routes
```

**Data loading rules:**

- Load `sites.json` and `scores.json` at start; load a site's `timeline`, `grid`, `windows` and `route` files only when that site is selected.
- Every screen handles three states: loading, "data not ready yet" (file missing), and ready.
- Until real data arrives, keep fake files in the same shapes in a local folder (not `shared/`, which other people own) and point the loaders at them with a single switch.

> **AI prompt:** "Using the brief and Section 2 (all schemas), set up a Vite React TypeScript app in web/ with publicDir '../shared'. Create types.ts for every schema, data/loaders.ts that fetches and caches each file with loading/missing/ready states, store.ts (Zustand) for selected site, date range and playback time, and App.tsx with a left navigation for: Mission Map, Light & Comms, Landing Windows, Rover Ops, Business, Copilot, Methods. Use a dark theme with CSS variables from theme.css. Explain the structure."

### 5.6 Design system

The look should say "mission control", not "school project".

- **Background:** near-black with a hint of blue; panels slightly lighter; thin borders.
- **Type:** one clean sans-serif (for example Inter) for text, one monospace for numbers and times.
- **Meaning colours, identical on every screen:** sunlight = warm amber, Earth contact = blue, both = green, danger/frozen = red, terrain = grey.
- **Never colour alone:** label everything ("Sunlit", "Earth in view", "FROZEN").
- **Headlines state findings:** "Site B: 11.5 usable days in March" beats "Results".
- **Numbers are tiles:** big value, small label, unit always shown.
- **Responsive:** works on a phone; check before every checkpoint.
- **Motion with purpose:** animate only things that change over time (shadows, rover, battery).

### 5.7 Screen 1: Mission Map (Core)

- A **south-polar image of the Moon** (NASA imagery is free to use: a south-polar mosaic from NASA's Moon Trek or LRO image pages), with an SVG overlay for markers.
- **Placing markers:** near the pole, distance from the centre is roughly proportional to `90 + lat` (lat negative) and direction follows longitude:
  ```
  r = (90 + lat) × k
  x = cx + r × sin(lon_radians)
  y = cy − r × cos(lon_radians)
  ```
  Calibrate `k`, `cx`, `cy` and the direction by lining up two features you can identify (ask your AI for a small calibration helper with draggable test points).
- Markers show rank badges from `scores.json`; hover shows the site card (name, usable days, longest dark spell, best landing); click selects the site everywhere.
- Side panel: the ranked site list.

### 5.8 Screen 2: Light & Comms (Core, NASA's core requirement, make it excellent)

For the selected site and a date range (default: 30 days from the scores window):

1. **Stat tiles:** % hours sunlit, % Earth visible, % both, longest dark spell, longest contact gap.
2. **Timeline bands:** three horizontal bands, one segment per hour: Sun (amber where `sun_frac ≥ 0.5`, partial shade for 0–0.5), Earth (blue where `earth_visible`), Both (green). Hover any hour: time, Sun and Earth elevation, terrain horizon, `sun_frac`.
3. **Elevation chart (Pro, very insightful):** lines for Sun elevation and the terrain horizon in the Sun's direction, shaded where the Sun is above the horizon; same for Earth. This *shows why* a site goes dark.
4. **Compare mode (Pro):** stack two or three sites with the same date range so the difference is obvious.

> **AI prompt:** "Build TimelineBands (SVG) for rows in schema 2.2: three bands (Sun, Earth, Both) with one segment per hour, amber/blue/green, partial amber opacity for sun_frac between 0 and 0.5, hover tooltip with time, elevations, horizons, sun_frac. Add StatTiles computing % sunlit (sun_frac ≥ 0.5), % earth_visible, % both, longest consecutive dark spell and longest contact gap in hours. Then build ElevationChart (Recharts) plotting sun_elev_deg vs sun_horizon_deg with the gap shaded. Support stacking up to three sites. Explain the longest-spell algorithm."

### 5.9 Screen 3: Landing Windows (Pro)

- **Heatmap:** rows = sites, columns = landing times across the year (from each `windows_SITE.json`), colour = usable days (dark = few, bright = many), crossed out where `survives` is false.
- Hover: landing time, usable days, sun/contact hours, longest dark spell. Click: jump to Light & Comms for that site and date.
- **"Best window" callouts:** top three landing times overall.
- **Cost of a slip (business tie-in):** for a chosen landing time, a small line chart of cost per usable day if landing slips 0–7 days.

### 5.10 Screen 4: Rover Ops (Core 2D, Insane 3D)

**2D (Core):**

- Canvas drawing the grid from `grid_SITE.json` at the current playback hour: lit cells light grey, shaded cells near-black, partial in between (from `sun_pct`); cells steeper than `max_slope_deg` hatched.
- All routes from `route_SITE.json` drawn as coloured lines; a rover marker moves along each.
- **Playback controls:** play/pause, speed (1×, 10×, 50× hours per second), time scrubber. Position at time t = the last step with `t_h ≤ t`, interpolated to the next step for smooth motion. The grid's shadows update with the hour (`depart_step + t`).
- **Battery panel:** a live bar per route plus a line chart of `battery_wh` over time with the reserve line marked.
- When a route reaches `frozen_at_index`: stop its marker, red **FROZEN** label, battery chart turns red.
- **Caption from the file:** "Shortest path froze after 9.3 h · Sunchaser arrived in 22 h with 21% battery left."

**Pro:**

- **Survival badges:** each route's `survival_probability` as a big percentage.
- **Pareto chart:** `pareto` points as duration vs survival probability, labelled by reserve %, so a planner can pick their risk level.

**Insane: 3D terrain:**

- react-three-fiber `PlaneGeometry` with `rows × cols` segments; vertex heights from `elevation_m` (vertical exaggeration ×2–3, labelled).
- Vertex colours from `sun_pct` at the current hour, so the shadows are the real computed ones and they **sweep across the terrain** as playback runs.
- Routes as 3D lines just above the surface; the rover as a small glowing model moving along its route.
- A directional light from the Sun's azimuth and elevation (from the timeline) for atmosphere; OrbitControls for the camera; a "follow rover" camera mode.

> **AI prompt:** "Build RoverCanvas (HTML canvas, React) for schemas 2.3 and 2.8: draw cells by sun_pct at hour floor(depart_step + t) (0 = near-black, 100 = light grey), hatch cells above max_slope_deg from rover.json, draw each route as a coloured polyline, move a marker along each route at time t (last step with t_h ≤ t, linearly interpolated), and show a red FROZEN label at frozen_at_index. Add play/pause, speed 1×/10×/50× and a scrubber via the Zustand store, plus a battery line chart per route with the reserve line. Explain the animation loop and how it stays smooth."

> **AI prompt (Insane):** "Build Terrain3D with react-three-fiber and drei: PlaneGeometry with rows×cols segments, vertex z from elevation_m × exaggeration, vertex colours from sun_pct at the current playback hour (updated each frame from the store), route polylines 2 m above terrain, a moving rover mesh, directional light from sun_az_deg/sun_elev_deg of the matching timeline row, OrbitControls and a follow-rover camera toggle. Keep it at 60 fps on a laptop; explain how you update colours efficiently."

### 5.11 Screens 5–7: Business, Copilot, Methods

**Business (Core):**

- Mission budget input (with a currency label).
- Ranked table from `scores.json`: usable days, contact hours, longest dark spell, survives, **cost per usable day**, **data returned**.
- Recommendation card: top site, best landing time, and its AI `brief`.
- Headline comparing the best and worst sites in one sentence.
- Pro: the cost-of-a-slip chart (shared with Landing Windows). Insane: the sensitivity chart.

**Copilot (Pro):**

- Chat panel calling `POST /api/copilot` (schema 2.9).
- Each answer shows **"facts used"** chips from `facts_used`, so users see it's grounded.
- Suggested questions as buttons: "Best site for a 10-day mission in March?", "Why does site A go dark on Feb 18?", "What does a 2-day slip cost at site B?".
- Friendly error state if the API isn't available.

**Methods (Pro, judges love it):**

- Data sources (JPL Horizons, LRO LOLA, NASA lighting maps, Moon Trek), with links.
- How each number is computed, in plain English, with the physics from Section 1.2.
- Validation (from Baldwin: comparison with real CLPS landings and NASA lighting maps).
- Assumptions and limitations; how we used AI; the team.

### 5.12 Deploying to Vercel

1. Sign in at vercel.com with GitHub; **import** `sunchaser`.
2. **Root directory:** the repo root (so `shared/` and Baldwin's `api/` folder are included).
3. **Build command:** `cd web && npm install && npm run build` · **Output directory:** `web/dist`.
4. **Environment variable** for the copilot: Baldwin tells you the name (e.g. the LLM provider's API key); add it under **Settings → Environment Variables**. Never put keys in the code.
5. **Production branch:** `main`. Pushes to `web-(Dhiran)` get preview links for testing.
6. Test the live link on a phone after every checkpoint merge.

### 5.13 Pitch package

**60-second demo video** (record after Sun 13:00: screen recording + voice-over + music at low volume)

1. **Hook (8 s):** the 3D terrain (or 2D grid) with shadows sweeping. "At the Moon's south pole, the Sun never rises more than a degree and a half. Robots here freeze in the dark."
2. **Where and when (15 s):** map → timeline lighting up → the landing-window heatmap. "Sunchaser scans every site and every landing time for a year."
3. **How to drive (20 s):** Rover Ops: the shortest route freezes, the Sunchaser route survives. "97% survival versus 4%." Cut to the real rover if built.
4. **What it's worth (12 s):** Business screen. "For the same budget, site B delivers 40% more usable days" (use real numbers).
5. **Close (5 s):** "Sunchaser, by Team Zenon. Built on NASA data."

**Slide deck (6–8 slides):** problem → why the south pole is hard → Sunchaser in one picture → the science (terrain, partial sun, Monte Carlo) → the demo moment → business value → validation and limits → team.

**README intro:** pitch, live link, problem in three sentences, the six modules, headline results, data sources, how we used AI.

**Team page text (doesn't give away the idea):**

> Team Zenon is taking on the Lunar Landing Site Navigator challenge at NASA Space Apps 2026. The Moon's south pole is where the next wave of commercial and Artemis missions is heading, and it's one of the hardest places in the solar system to operate: the Sun barely rises, shadows never stop moving, and every hour of light matters. We're building a tool that helps lunar missions make smarter decisions about where to go and when, using real NASA data on lighting, terrain and communication. Our approach mixes engineering, robotics, AI and a business mindset, because getting to the Moon is only half the problem. Staying useful once you're there is the other half.

### 5.14 Self-checks before every merge

- [ ] Every screen handles loading, missing data and ready states.
- [ ] Colours mean the same thing everywhere; nothing relies on colour alone.
- [ ] Every number on screen has a unit and comes from a file (no hard-coded results).
- [ ] Works on a phone.
- [ ] No API keys in the code.
- [ ] `rover.json` and `criteria.json` match schemas 2.6 and 2.7 exactly; `SOURCES.md` covers every number.

---

## 6. Prep before the event (no project code)

- [ ] Accept the GitHub invite, clone, switch to `web-(Dhiran)`, practise one commit and push with a throwaway file.
- [ ] Read the full challenge statement (Section 1.1).
- [ ] Research rover specs and draft `rover.json` + `SOURCES.md` notes (5.2).
- [ ] Draft `criteria.json` (5.3) and talk it through with Baldwin and Harril.
- [ ] Learn about CLPS and the companies flying under it; draft the business slides (5.4).
- [ ] In a throwaway project: a Vite + React + TypeScript app with one chart and one canvas animation, deployed to Vercel.
- [ ] If you'll attempt 3D: one react-three-fiber tutorial (a terrain or heightmap demo).
- [ ] Sketch all seven screens on paper; pick fonts and the exact colour values.
- [ ] Find and save a south-polar Moon image for the map.
- [ ] Storyboard the 60-second video.

---

## 7. Weekend schedule

| When | Goal |
| --- | --- |
| Sat 09:00–10:00 | Team agrees schemas; commit final `rover.json` and `criteria.json`; tell Harril and Baldwin |
| Sat 10:00–12:00 | App scaffold, types, loaders, theme, navigation; deployed to Vercel with fake data |
| **Sat 12:00** | **Checkpoint:** pull request |
| Sat 12:00–18:00 | Mission Map + Light & Comms (make the timeline excellent) |
| **Sat 18:00** | **Checkpoint:** update from main; real timeline data live = minimum viable submission |
| Sat 18:00–24:00 | Rover Ops 2D playback; Business dashboard. Then sleep. |
| Sun 08:00–10:00 | Landing Windows heatmap, compare mode, survival badges |
| **Sun 10:00** | **Checkpoint:** real routes, scores and windows live |
| Sun 10:00–13:00 | Copilot chat, Methods page, Pareto chart; 3D only if all Pro is done |
| **Sun 13:00** | **Feature freeze:** record the video, finish slides and README intro, check the submission form |
| Sun afternoon | Submit well before your local event's deadline |

---

## 8. Done means

- [ ] `shared/rover.json` and `shared/criteria.json` committed; every number sourced or labelled estimate in `web/SOURCES.md`.
- [ ] Live Vercel link that works on a phone.
- [ ] Core screens (Map, Light & Comms, Rover Ops 2D, Business) on real data.
- [ ] Pro screens as far as time allowed (Landing Windows, Copilot, Methods).
- [ ] Business slides with real headline numbers.
- [ ] 60-second video, slide deck, README intro.
- [ ] Everything committed and merged into main.

## Interview questions you must be able to answer

1. Why is the lunar south pole so hard to operate in, and why are the panels vertical?
2. Where does each rover number come from, and what were your sanity checks?
3. What exactly is a usable day, and why those thresholds?
4. Who pays for Sunchaser, and how do cost per usable day and the cost of a slip work?
5. Walk me through your web app architecture and how it handles a year of hourly data per site.
6. How do you know the AI copilot isn't making numbers up?
