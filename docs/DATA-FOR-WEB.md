# What's in `shared/` and `/api/copilot`: a guide for the web app

Written by the data and planner side for Dhiran. Nothing here changes the data contract in `CLAUDE.md`
Section 2; it tells you what is actually in the files today, how big they are, and the few things that are
easy to get wrong.

## Files (all on `main`, all real NASA-derived data)

| File | Count | Size each | Load when |
| --- | --- | --- | --- |
| `sites.json` | 1 | 4 KB | app start |
| `scores.json` | 1 | 5 KB | app start |
| `timeline_SITE.json` | 9 | 2.1 MB | a site is selected |
| `windows_SITE.json` | 9 | 0.2 MB | Landing Windows / Business screens |
| `grid_SITE.json` | 9 | 3.8-5.1 MB | Rover Ops, for the selected site only |
| `route_SITE.json` | 9 | 15-25 KB | Rover Ops |

Site ids are names, not `site_a`: `cabeus_b_peak`, `haworth`, `malapert_massif`, `mons_mouton_plateau`,
`mons_mouton`, `nobile_rim_1`, `nobile_rim_2`, `de_gerlache_rim_2`, `slater_plain`. Read them from
`sites.json`; don't hard-code them.

## Things that are easy to get wrong

1. **Longitudes can be negative** (`-67.665` means 67.665° W). For the map marker formula use
   `lon_radians = lon * π / 180` as is; `sin` and `cos` handle the sign.
2. **Timelines cover all of 2027 (8,760 rows).** Slice by date for the default 30-day view; don't render all
   8,760 segments at once on a phone.
3. **`sun_frac` is 0-1; `sun_pct` in grids is 0-100.** "Sunlit" everywhere in our numbers means
   `sun_frac ≥ 0.5` (or `sun_pct ≥ 50`).
4. **`dsn_station`** is `"Goldstone"`, `"Madrid"`, `"Canberra"` or `null` (Earth hidden, or no dish can see the
   Moon). **`surface_temp_k`** is filled in (kelvin, model output, context only).
5. **Grids are 64 x 64 cells of 80 m** (5.1 km across), not 40 m: read `cell_size_m` from the file. Each site's
   grid covers a different 14-day window (`window_start`), chosen by searching 2027 for that site's most
   telling rover scenario.
6. **Grid orientation:** row 0 is the top, column 0 is the left, and 0° longitude points up, the same as a
   south-polar map image. Local north is NOT up: `orientation_note` says how many degrees clockwise from the
   top it points at that site.
7. **Routes:** `depart_step` is the hour index into the grid (24 for every site: the rover leaves one day into
   the window). A step's `t_h` is hours since departure, so the grid frame to draw at playback time `t` is
   `sun_pct[floor(depart_step + t)]`.
8. **A frozen route's last step** is where the battery hit zero (`frozen_at_index` = last index,
   `battery_wh` = 0). It may be part-way through a move.
9. **`survival_probability`** counts a run as survived only if the rover never froze on the way **and** stayed
   alive for 24 hours parked at the destination. Show it as a percentage.
10. **`sunchaser_safe` and `pareto` can be missing** for a site if no safer route exists; handle that.
11. **`scores.json` ranks by survival first, then usable days.** A site whose best landing isn't survivable
    ranks last even if it has many usable days on paper (`survives: false`).
12. **Everything currently uses placeholder rover and criteria values** (the examples in `CLAUDE.md` 2.6 and
    2.7). When you commit `shared/rover.json` and `shared/criteria.json`, tell Baldwin: scores, windows, grids
    and routes are regenerated with a few commands.

## The copilot

`POST /api/copilot` with `{"question": "...", "site": "slater_plain"}` (`site` optional). Always answers
`200` with `{"answer": "...", "facts_used": [{"label": "...", "value": "..."}]}` unless the request itself is
bad (`400`) or one address sends more than 10 questions a minute (`429`); errors look like `{"error": "..."}`.

It works with no API key at all (a rule-based fact finder answers). With `GEMINI_API_KEY` set in Vercel it
uses Google's free Gemini tier first and falls back to the fact finder. Details: `api/README.md`.

Good suggested-question buttons (all answered instantly by the fact finder):
- "Which site is best in June?"
- "When should we land at Malapert in March?"
- "How dark does Haworth get in August?"
- "What does a 3-day slip cost at Malapert with a $40 million budget?"
- "Does the rover survive at Slater Plain?"
- "Best landing for a 5-day mission at Mons Mouton in June?"

## Vercel

- Project root = the repo root (so `shared/` and `api/` deploy with the site). Build command
  `cd web && npm install && npm run build`, output `web/dist`.
- `vercel.json` and `requirements.txt` at the repo root belong to the copilot. Don't add a web framework to
  `requirements.txt`: Vercel would then treat the whole project as a Python app and stop serving the site.
- In `web/vite.config.ts`, `publicDir: '../shared'` makes `fetch('/sites.json')` work in dev and in the build.

## Numbers you can quote (they come from the files; regenerate with `python data/update_readme.py`)

See "Headline results" in the root `README.md`.
