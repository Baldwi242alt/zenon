# Harril: what to do now

The planner code is finished and on `main` and on your branch `planner-(Harril)`. These are the things only
you can do. Suggested order for tonight: 1, then 2, then 3, then 4 if you have the parts.

## 1. Get the latest code

1. GitHub Desktop: switch to `planner-(Harril)`.
2. **Fetch origin**, then **Pull origin**.
3. Open the repo folder in VS Code (**Repository → Open in Visual Studio Code**).

Your files are in `planner/` and `hardware/`. Your output files are `shared/route_*.json`.

## 2. Learn the planner so you can present it (about an hour)

Most of your files were rewritten on top of your physics and A* code, so read them before judges ask.

1. Read `planner/README_planner.md` from top to bottom. It explains every part in plain English.
2. Run the tests:
   ```bash
   python -m pytest planner/tests
   ```
3. Plan one site yourself and read the printed result:
   ```bash
   python planner/run.py --site slater_plain
   ```
4. Open these files in this order and read the comments at the top of each:
   - `planner/sunchaser/physics.py` (your equations, plus `power_out_w`)
   - `planner/sunchaser/world.py` (allowed moves, and the one battery step used everywhere)
   - `planner/sunchaser/sim.py` (replays a route)
   - `planner/sunchaser/astar2d.py` (shortest route)
   - `planner/sunchaser/astar_st.py` (the Sunchaser planner)
   - `planner/sunchaser/montecarlo.py`, `pareto.py`, `replan.py`

### Be able to answer these

1. Why does the shortest route fail at the lunar south pole?
2. Walk through the energy model. Why do heaters matter more than hills?
   (Flat driving costs 3.2 W of mechanical power, a 15° climb 8.7 W, staying alive in the dark 90 W.)
3. How does A\* work, and why must the heuristic never overestimate?
4. Why are time and battery energy part of the search state? What is dominance pruning?
5. Why report survival as a probability? What is randomised in the 500 runs?
6. What is the trade-off between the fast and the safe route?
7. What does "arriving safely" mean? (The rover must be able to park at the target for 24 hours
   without dropping below its reserve.)
8. What is simplified, and what would you change to fly this on a real rover?

The answers are all in `planner/README_planner.md`.

### Numbers to know (they come from `shared/route_*.json`)

| Site | Shortest route | Sunchaser |
| --- | --- | --- |
| Slater Plain | freezes after 17.1 h (10% survival) | arrives in 20.5 h (100%) |
| de Gerlache Rim 2 | freezes after 16.5 h (0%) | arrives in 23.4 h (100%) |
| Nobile Rim 2 | freezes after 20.1 h (0%) | arrives in 26.1 h (96%) |
| Mons Mouton Plateau | freezes after 16.0 h (1%) | arrives in 24.4 h (100%) |

At 7 of 9 sites the shortest route freezes and Sunchaser arrives. Malapert is the honest exception: no
trip was found there where the shortest route freezes.

These use the placeholder rover from the handbook (2,000 Wh battery, 245 W panel, 200 m/h). The numbers
will change when the real rover specifications are committed and the planner is rerun.

## 3. Check the demo scenario

Look at the Slater Plain routes and decide whether this is the story you want to tell.

1. See the summary:
   ```bash
   python planner/run.py --site slater_plain
   ```
2. If you want a different start, target or departure hour, try it (rows and columns are 0-63):
   ```bash
   python planner/run.py --site slater_plain --start 18,32 --target 58,5 --depart 24
   ```
   This rewrites `shared/route_slater_plain.json`. If you keep a change, commit and push it. If you
   don't, discard the change in GitHub Desktop (right-click the file → **Discard changes**).
3. The replanning demo (panel output drops 30% part-way) is in `planner/out/replan_slater_plain.json`.

## 4. Build and test the physical rover (only if you have the parts)

This has only been tested in software. Nobody has run it on a real robot yet.

Parts: Arduino Uno, 2WD robot car chassis, L298N motor driver, motor battery pack, light sensor (LDR) with
a 10 kΩ resistor, USB cable.

1. Try the whole loop without hardware first:
   ```bash
   python hardware/bridge.py --site slater_plain --simulate --fast
   ```
2. Wire the rover as described at the top of `hardware/rover/rover.ino`.
3. Upload `hardware/rover/rover.ino` with the Arduino IDE.
4. Calibrate: time one cell forward and one 45° turn on your floor, then set `MS_PER_CELL` and
   `MS_PER_45_DEG` at the top of the sketch and upload again.
5. Read the light sensor covered and under the lamp (Arduino Serial Monitor shows `LIGHT <number>`).
6. Install the two libraries and run it, using your own port and your two light readings:
   ```bash
   pip install pyserial matplotlib
   ```
   ```bash
   python hardware/bridge.py --site slater_plain --port COM5 --dark 80 --lamp 900 --plot
   ```
7. Film the rover following the route, with the lamp as the Sun.

If something fails, copy the exact error message and send it to Baldwin.

## 5. Write your part of the README

Add a short robotics section to the root `README.md` in your own words (the facts are in
`planner/README_planner.md`):

- the rover model and the energy insight;
- how the planner works;
- what the Monte Carlo runs randomise;
- one headline result, for example Slater Plain;
- what is simplified.

Commit and push to `planner-(Harril)`, then tell Baldwin so he can merge it.
