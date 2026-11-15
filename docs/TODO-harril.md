# Harril: exactly what to do now

**Sunchaser · Team Zenon · robotics lead**

The planner code is finished. It is on `main` and on your branch `planner-(Harril)`. This file tells you,
step by step, what is left that only you can do. You don't need an AI assistant for any of it: every
command, every expected output and every answer you need is written here.

Do the parts in this order: **A → B → C → D**. Part E (the physical rover) is optional.

| Part | What | Time |
| --- | --- | --- |
| A | Get the code and check it runs on your PC | 15 min |
| B | Understand what changed in your files | 20 min |
| C | Learn the planner well enough to present it | 60 min |
| D | Check the demo scenario and write your README section | 30 min |
| E | Build and test the physical rover (optional) | 2-3 h |

Your folders: `planner/` and `hardware/`. Your output files: `shared/route_*.json`.
Don't edit anything in `data/`, `api/`, `web/`, or any other file in `shared/`.

---

## Part A: get the code and check it runs

### A1. Pull the latest code

1. Open **GitHub Desktop**.
2. Top bar, **Current repository**: `zenon`.
3. Top bar, **Current branch**: click it and choose `planner-(Harril)`.
4. Click **Fetch origin** (top right). The button changes to **Pull origin**. Click it.
5. If it says "Your branch is up to date" straight away, that's fine too.

If GitHub Desktop says you have local changes that would be overwritten: click **Stash changes and continue**.
Your old files are safe in the stash; the new versions replace them.

### A2. Open the folder

1. In GitHub Desktop: **Repository → Open in Visual Studio Code**.
2. In VS Code: **Terminal → New Terminal**. A terminal opens at the bottom, already in the repo folder.
   Every command below is typed there.

### A3. Install what the planner needs

```bash
pip install numpy pytest
```

If `pip` isn't found, try `python -m pip install numpy pytest`.
You need Python 3.11 or newer. Check with `python --version`.

### A4. Run the tests

```bash
python -m pytest planner/tests
```

**Expected:** the last line says `37 passed` (in about 2 seconds).

- If you see `No module named pytest`: do A3 again.
- If you see `No module named numpy`: do A3 again.
- If some tests fail: copy the whole output and send it to Baldwin. Don't try to fix it yourself.

### A5. Plan one site yourself

```bash
python planner/run.py --site slater_plain
```

**Expected output** (the numbers should match exactly):

```
Rover: PLACEHOLDER rover (planner/fake/rover_fake.json, the handbook's example values; shared/rover.json not committed yet)
   reserve 15%: ok, 8,715 labels, 0 s
   reserve 30%: ok, 8,704 labels, 0 s
   reserve 45%: ok, 8,681 labels, 0 s
slater_plain: (18, 32) -> (58, 5), depart step 24  [1 s, 9 KB]
   shortest: FROZE at 17.1 h after 3.42 km (p_survive 0.10)
   sunchaser_fast: 20.5 h, 4.09 km, min battery 51%, p_survive 1.00
```

How to read it:
- `(18, 32) -> (58, 5)`: start cell and target cell, as (row, column). Rows count down from the top, columns
  from the left, both from 0 to 63.
- `depart step 24`: the rover leaves 24 hours after the grid's first hour.
- `shortest: FROZE at 17.1 h after 3.42 km`: the naive route's battery hit zero 17.1 hours in.
- `p_survive 0.10`: in 500 simulated runs, 10% survived.
- `sunchaser_fast: 20.5 h, 4.09 km, min battery 51%`: the sun-chasing route arrives after 20.5 hours, drives
  0.67 km further, and its battery never drops below 51%.
- The three `reserve` lines are the planner run at three safety margins. Here all three found the same route,
  so only one Sunchaser route is listed.

This command rewrites `shared/route_slater_plain.json` with identical content, so GitHub Desktop should show
no changes afterwards.

---

## Part B: what changed in your files

Your physics equations and your A\* ideas are kept. The structure around them was rebuilt because the
original could not run end to end. Know these changes, because a judge may ask "what was hard?".

| File | What it was | What it is now |
| --- | --- | --- |
| `planner/sunchaser/physics.py` | Your 5 functions | Same 5 functions, plus `power_out_w` (your `sim.py` called it but it didn't exist) and `dark_endurance_h` |
| `planner/sunchaser/world.py` | Didn't exist | New. Holds the grid and rover, the list of allowed moves, and `advance()`: the single battery step used by both the simulator and the planner |
| `planner/sunchaser/sim.py` | Simulated driving only, crashed on `power_out_w` | Replays any plan made of `start`, `move` and `wait` steps, exactly, split at hour boundaries |
| `planner/sunchaser/astar2d.py` | Blocked a move only if the destination cell was steep | Blocks a move if either cell is steep, or the slope along the move is too steep. Adds tie-breaking |
| `planner/sunchaser/astar_st.py` | No dominance pruning; waits were never simulated; used a different energy rule from the simulator | Dominance pruning, real waits, the same energy rule as the simulator, the safe-arrival rule |
| `planner/sunchaser/montecarlo.py`, `pareto.py`, `replan.py`, `io.py` | Didn't exist | New |
| `planner/run.py` | Ran on fake data and printed to screen | Reads the real grid, writes `shared/route_SITE.json`, checks it |
| `planner/find_scenarios.py` | Didn't exist | New. Searches all of 2027 for each site's demo scenario |
| `planner/tests/` | 4 tests | 37 tests |
| `hardware/` | Didn't exist | Arduino sketch, laptop bridge, tests |
| `planner/fake/` | Your fake world | Unchanged. `rover_fake.json` is used as the placeholder rover |

Three bugs in the original that you should be able to describe:
1. **`sim.py` called `physics.power_out_w`, which didn't exist**, so the simulator crashed on its first line of
   logging.
2. **The planner and the simulator disagreed.** The planner charged a move's energy using the sunlight of the
   cell the rover was leaving; the simulator used the cell it was entering. A route the planner called safe
   could fail when replayed. Now both call the same function (`World.advance`), and a move spends its first
   half in the old cell and its second half in the new one.
3. **Waiting was planned but never simulated.** `run.py` threw away the wait steps and simulated nonstop
   driving, so a route that survived by waiting looked like it froze.

---

## Part C: learn the planner

### C1. Read these, in this order

1. `planner/README_planner.md`, top to bottom. This is the main explanation.
2. The comment block at the top of each file, then skim the code:
   1. `planner/sunchaser/physics.py`
   2. `planner/sunchaser/world.py`
   3. `planner/sunchaser/sim.py`
   4. `planner/sunchaser/astar2d.py`
   5. `planner/sunchaser/astar_st.py`
   6. `planner/sunchaser/montecarlo.py`
   7. `planner/sunchaser/pareto.py`
   8. `planner/sunchaser/replan.py`
3. `planner/tests/test_spacetime.py`: each test is a tiny world where the right answer is known by hand.
   Read `test_shortest_route_freezes_in_the_shadow_and_sunchaser_waits_it_out` carefully; it is the whole
   project in 20 lines.

### C2. The rover's numbers (placeholder rover, from the handbook)

| Quantity | Value | How it's worked out |
| --- | --- | --- |
| Mass | 120 kg | given |
| Battery | 2,000 Wh, reserve 15% = 300 Wh | given |
| Peak solar power | 245 W | 1361 × 0.6 m² × 0.30 |
| Power parked in sunlight | 30 W | avionics only |
| Power parked in the dark | 90 W | 30 W avionics + 60 W heater |
| Drive power, flat ground | 43.2 W | 40 W base + 3.24 W mechanical |
| Drive power, 15° uphill | 48.7 W | 40 W base + 8.72 W mechanical |
| Speed | 200 m/h | given. One 80 m cell takes 0.4 h; a diagonal takes 0.566 h |
| Charging, parked in full Sun | 204 Wh per hour | (245 − 30) × 0.95 |
| Dark endurance, parked | 18.9 h to the reserve, 22.2 h to empty | 1,700 ÷ 90 and 2,000 ÷ 90 |
| Driving in the dark | 133 W, so 15 h to empty | 30 + 60 + 43.2 |

These are placeholders. When the real rover specifications are committed to `shared/rover.json`, the planner
is rerun and every number below changes.

### C3. The questions you must be able to answer, with the answers

**1. Why does the shortest route fail at the lunar south pole?**
The Sun is never more than about 1.5° above the horizon, so every hill casts a shadow kilometres long, and
the shadows move as the Sun circles the sky once every 29.5 days. The shortest route ignores them. In shadow
the rover gets no solar power and must run 60 W of heaters to survive, so it draws 133 W while driving. A full
2,000 Wh battery lasts 15 hours of that. A 4 km traverse takes 20 hours. If most of it is in shadow, the
battery hits zero on the way.

**2. Walk me through the energy model. Why do heaters matter more than hills?**
Power in = 1361 W/m² × panel area × efficiency × the visible fraction of the Sun's disk. Power out = avionics
+ heater (on when the Sun is under 5%) + drive power. Drive power = base + mass × gravity × speed × (rolling
resistance × cos slope + sin slope) ÷ drivetrain efficiency. At 200 m/h the rover moves at 0.056 m/s, so the
mechanical part is tiny: 3.2 W on the flat and 8.7 W up a 15° slope. Staying alive in the dark costs 90 W.
So the planner's job is to avoid darkness, not hills. Slope only matters as a safety limit (nothing steeper
than 15°).

**3. How does A\* work, and why must the heuristic never overestimate?**
A\* keeps a priority queue of places to explore, ordered by f = g + h: the cost so far plus an estimate of the
cost still to go. It always expands the lowest f first. If h never overestimates the true remaining cost,
then when the target comes off the queue no unexplored route can be cheaper, so the answer is optimal. If h
overestimated, A\* could skip the true best route. We use the octile distance: the length of the best route on
an empty grid where you can move in 8 directions. Obstacles only make real routes longer, so it never
overestimates.

**4. Why are time and battery energy part of the search state?**
Because the same cell is a different place at a different hour (lit now, dark later) and with a different
battery (a full rover can cross a shadow that kills a half-empty one). So a state is (cell, time, energy). From
each state the rover can move to a neighbour or wait 1 hour or half an hour. Any action that takes the battery
below the reserve is thrown away.

**5. What is dominance pruning and why does it keep the search tractable?**
With time and energy in the state there are thousands of ways to reach each cell at slightly different times
and charges. Most are pointless. Label A dominates label B at a cell if A arrived no later than B and, by
simply waiting there until B's arrival time, A would have at least as much energy as B. Then anything B can do,
A can do, so B is dropped. Each cell keeps only its non-dominated labels.
Example: A reaches a sunlit cell at hour 3.0 with 1,500 Wh; B reaches it at hour 3.4 with 1,520 Wh. A, waiting
0.4 hours in the Sun, gains 0.4 × 204 = 82 Wh and has 1,582 Wh at hour 3.4. That beats B, so B is dropped.
Proof it's safe: a test runs the planner with pruning switched off (brute force) on small random worlds and
checks the arrival time is identical.

**6. Why report survival as a probability? What did you randomise?**
Real hardware never matches its spec sheet. Each route is replayed 500 times. Each run multiplies battery
capacity, solar panel output and power draw by a random factor (normal distribution, 10% standard deviation,
clipped to 0.5-1.5) and delays departure by a random 0 to 2 hours. Survival probability is the share of runs
in which the rover never froze, on the way or in the 24 hours parked at the destination. The random seed is
fixed (42) so anyone rerunning the code gets the same number.

**7. What does "arriving safely" mean?**
Reaching the target only counts if the rover could then stay parked there for 24 hours without dropping below
its reserve. Without this rule, an early version "arrived" in the dark with 15% battery, three hours from
freezing.

**8. What is the trade-off between the fast and the safe route?**
The planner keeps the battery above a reserve. A 15% reserve lets the rover push through marginal conditions
and arrive sooner. A 45% reserve makes it detour and wait more, arriving later but with far more margin if
something goes wrong. Example at Nobile Rim 2: the fast route takes 26.1 h with 96% survival; the safe route
takes 28.1 h with 100%. Two extra hours buy four points of survival. A mission team picks its own risk level
from that menu.

**9. What is simplified, and what would you change to fly this?**
Simplified: no wheel slip; the heater is on or off, not driven by temperature; the rover starts full and
doesn't transmit while driving; 80 m cells and 45° turns; waits come in 1 h and 0.5 h steps.
To fly it: a wheel-soil model, a thermal model driving heater power, communication windows as a constraint,
on-board replanning when measured power differs from the plan, finer terrain near the route, and terrain
uncertainty in the Monte Carlo runs.

**10. Why is the grid 5.1 km across with 80 m cells?**
The first grids were 2.56 km across. On those, the rover's battery never fell below 48% on any crossing at any
site: no crossing takes longer than about 15 hours and the rover lasts about 22 hours in the dark, so nothing
could fail. The area was enlarged to 5.1 km, where traverses take 20 to 35 hours. The rover's specifications
were not changed to create drama.

**11. How were the demo scenarios chosen?**
By search, not by hand. For each site, `planner/find_scenarios.py` tries start/target pairs at least 3.8 km
apart on gentle ground, with a departure every 12 hours across all of 2027. It keeps cases where the rover
starts in sunlight, the target can host a parked rover, and the shortest route freezes. The most promising are
planned with Sunchaser and scored by the gap in survival probability. Results are in `planner/scenarios.json`.

### C4. The results (from `shared/route_*.json`)

| Site | Shortest route | Sunchaser (fastest safe) | Sunchaser (max margin) |
| --- | --- | --- | --- |
| Slater Plain | freezes after 17.1 h, 10% survival | arrives in 20.5 h, 100% | same route |
| de Gerlache Rim 2 | freezes after 16.5 h, 0% | arrives in 23.4 h, 100% | same route |
| Nobile Rim 2 | freezes after 20.1 h, 0% | arrives in 26.1 h, 96% | arrives in 28.1 h, 100% |
| Mons Mouton Plateau | freezes after 16.0 h, 1% | arrives in 24.4 h, 100% | arrives in 24.7 h, 100% |
| Nobile Rim 1 | freezes after 15.7 h, 5% | arrives in 19.6 h, 100% | same route |
| Mons Mouton | freezes after 16.5 h, 3% | arrives in 20.6 h, 97% | same route |
| Haworth | freezes after 19.8 h, 33% | arrives in 22.5 h, 100% | same route |
| Peak near Cabeus B | arrives in 20.0 h, but only 2% survive | arrives in 24.6 h, 95% | arrives in 30.3 h, 100% |
| Malapert Massif | arrives in 23.5 h, 71% | arrives in 23.5 h, 80% | same route |

The one-line summary: **at 7 of 9 sites the shortest route freezes and Sunchaser arrives.**

Two honest details to mention if asked:
- **Cabeus B:** the shortest route does reach the target, with 8% battery, and then dies; only 2% of runs
  survive the following 24 hours.
- **Malapert:** it is 62% steep slopes, so few long trips are drivable, and no trip was found where the
  shortest route freezes. The two routes are nearly the same there.

### C5. The Slater Plain demo, in detail

- Grid: 64 × 64 cells of 80 m, 14 days starting 30 October 2027, 00:00 UTC.
- Start cell (18, 32), target cell (58, 5), departure at hour 24 (31 October 2027, 00:00 UTC).
- **Shortest route:** 32 moves, 3.42 km planned to the point where it dies. The battery hits zero after
  17.1 hours. It drew 2,134 Wh in total.
- **Sunchaser route:** 40 moves, 4.09 km, arrives after 20.5 hours. Lowest battery 51%. It drew 1,998 Wh.
- **How Sunchaser wins here:** by detouring 0.67 km through sunlit ground. It does not need to wait at this
  site. (Waiting shows up at other sites and in the tests; say "detours around the shadow" for Slater.)
- **Replanning demo** (`planner/out/replan_slater_plain.json`): 11.2 hours in, at cell (38, 13) with 1,141 Wh,
  panel output drops 30%. Both carrying on and replanning arrive at 20.5 hours with about 57% minimum battery,
  because by then the route is mostly lit and the rover has plenty of margin. Honest reading: this scenario
  has enough margin that the fault doesn't change the route.

---

## Part D: check the demo and write your section

### D1. Decide whether Slater Plain is the story you want

Slater Plain is the default demo because only 2% of its cells are too steep to drive. If you'd rather show a
site where the fast and safe routes differ, use Nobile Rim 2 or Mons Mouton Plateau.

To try a different start, target or departure at any site (rows and columns are 0 to 63, departure is an hour
from 0 to about 300):

```bash
python planner/run.py --site slater_plain --start 18,32 --target 58,5 --depart 24
```

Site names you can use: `cabeus_b_peak`, `haworth`, `malapert_massif`, `mons_mouton_plateau`, `mons_mouton`,
`nobile_rim_1`, `nobile_rim_2`, `de_gerlache_rim_2`, `slater_plain`.

- If it prints `no drivable route`, the start or target is on steep ground or cut off. Try nearby cells.
- If it prints `no safe Sunchaser route exists in this window`, that trip can't be done safely. Try another.
- This command **rewrites** `shared/route_SITE.json`.
  - To keep your change: GitHub Desktop → tick the file → summary "Change demo route for SITE" →
    **Commit to planner-(Harril)** → **Push origin** → tell Baldwin.
  - To undo it: GitHub Desktop → right-click the file → **Discard changes**.

Don't run `python planner/run.py --all` unless Baldwin asks: one site (Malapert) takes about 7 minutes.

### D2. Write your README section

1. Open `README.md` at the top of the repo.
2. Find the line `## Team Zenon` near the bottom.
3. Above it, add a new section with the heading `## Robotics (Harril)`.
4. Write it in your own words. Cover these five points, 2 to 4 sentences each:
   1. The rover model and the energy insight (heaters, not hills).
   2. How the planner works (states with time and energy, move or wait, the reserve, dominance pruning).
   3. What the Monte Carlo runs randomise and why survival is a probability.
   4. One headline result. Suggested: "At Slater Plain, departing 31 October 2027, the shortest route froze
      after 17.1 hours (10% survival). Sunchaser arrived in 20.5 hours with a 100% survival probability."
   5. What is simplified.
5. Save. GitHub Desktop → summary "Add robotics section to README" → **Commit to planner-(Harril)** →
   **Push origin**.
6. Tell Baldwin it's pushed so he can merge it into `main`.

Don't edit the block between `<!-- RESULTS:START -->` and `<!-- RESULTS:END -->`: a script regenerates it.

---

## Part E (optional): build and test the physical rover

**Status:** the Arduino sketch and the laptop bridge are written. The laptop side is tested in software.
Nobody has run it on a real robot. Expect to debug wiring and calibration.

### E1. Try the whole loop without hardware first

```bash
python hardware/bridge.py --site slater_plain --simulate --fast
```

**Expected:** a list of commands with battery levels, ending with a line like
`[  21.3 h] route complete, battery 2000 Wh`.

To see only the commands the rover will receive:

```bash
python hardware/bridge.py --site slater_plain --commands
```

The first lines are `L 180`, `F 1.00`, `R 45`, `F 31.02`, ... (`F` = forward that many cells, `L`/`R` = turn
that many degrees, `W` = wait that many seconds).

### E2. Parts

Arduino Uno (or compatible), 2-wheel robot car chassis with two DC motors, L298N motor driver, battery pack
for the motors (4 × AA or a 7.4 V pack), one light-dependent resistor (LDR), one 10 kΩ resistor, jumper
wires, USB cable.

### E3. Wiring

| From | To |
| --- | --- |
| L298N IN1 | Arduino pin 5 |
| L298N IN2 | Arduino pin 6 |
| L298N IN3 | Arduino pin 9 |
| L298N IN4 | Arduino pin 10 |
| L298N ENA | Arduino pin 3 (remove the ENA jumper on the L298N first) |
| L298N ENB | Arduino pin 11 (remove the ENB jumper first) |
| L298N OUT1, OUT2 | left motor |
| L298N OUT3, OUT4 | right motor |
| L298N 12V | motor battery + |
| L298N GND | motor battery − **and** Arduino GND (the grounds must be joined) |
| LDR leg 1 | Arduino 5V |
| LDR leg 2 | Arduino A0 |
| 10 kΩ resistor | between Arduino A0 and GND |

### E4. Upload the sketch

1. Install the **Arduino IDE** if you don't have it.
2. **File → Open** → `hardware/rover/rover.ino`.
3. **Tools → Board → Arduino Uno**. **Tools → Port** → the port that appears when you plug the Uno in
   (for example `COM5`). Write this port name down.
4. Click **Upload** (the arrow button). Wait for "Done uploading".
5. **Tools → Serial Monitor**, set the speed (bottom right) to **115200**. You should see `READY`, then
   `LIGHT 512` style lines ten times a second.

### E5. Calibrate

1. **Light sensor.** In the Serial Monitor, cover the LDR with your hand and note the `LIGHT` number (the dark
   reading). Shine your lamp on it and note the number (the lamp reading). The lamp reading must be higher.
   If it's lower, swap the LDR and the resistor.
2. **Driving.** Put the rover on the floor. Type `F 1` in the Serial Monitor and press Enter. It should drive
   forward briefly and print `DONE`.
   - If it drives backward, swap that motor's two wires on the L298N.
   - If it spins, one motor is reversed: swap that motor's wires.
   - Decide how long one "cell" is on your printed map (for example 5 cm). Adjust `MS_PER_CELL` at the top of
     the sketch until `F 1` moves exactly one cell. Larger number = further.
3. **Turning.** Type `R 45`. Adjust `MS_PER_45_DEG` until it turns exactly 45°.
4. Upload again after each change.
5. **Close the Serial Monitor** before the next step. Only one program can use the port.

### E6. Run it

Install the two libraries once:

```bash
pip install pyserial matplotlib
```

Then run, replacing `COM5` with your port, `80` with your dark reading, `900` with your lamp reading, and
`1200` with your `MS_PER_CELL`:

```bash
python hardware/bridge.py --site slater_plain --port COM5 --dark 80 --lamp 900 --ms-per-cell 1200 --plot
```

What should happen:
- The rover turns and drives the route, command by command.
- A window plots the simulated battery, with a dashed line at the 300 Wh reserve.
- Lamp on the sensor: the battery line rises. Sensor shaded: it falls.
- If the battery drops below the reserve while the sensor is lit, the laptop sends `STOP`; the rover parks and
  recharges; then the laptop sends `GO`.
- In the dark it keeps driving on purpose: stopping there would only drain the battery.

The route is 4 km on the Moon, which is about 51 cells. Check your printed map or floor has room, or use a
shorter cell length.

### E7. If something goes wrong

| Problem | Fix |
| --- | --- |
| `could not open port` | Close the Arduino Serial Monitor; check the port name |
| `No module named serial` | `pip install pyserial` |
| Rover doesn't move, `LIGHT` lines appear | Motor battery not connected, or grounds not joined, or ENA/ENB jumpers still on |
| Rover moves but never prints `DONE` | Re-upload the sketch; check the baud rate is 115200 |
| Battery line never rises under the lamp | `--dark` and `--lamp` values are swapped or wrong; redo E5 step 1 |
| Anything else | Copy the exact error text and send it to Baldwin |

### E8. Film it

Film 10 to 15 seconds of the rover following the route with the lamp as the Sun, and the battery plot visible
on the laptop behind it. Shade the sensor once so the line dips, then light it again.

---

## Checklist

- [ ] A4: `37 passed`
- [ ] A5: output matches
- [ ] B: can describe the three bugs
- [ ] C3: can answer all 11 questions without looking
- [ ] C4: knows the one-line summary and the two honest details
- [ ] D1: demo site confirmed (or changed, committed and pushed)
- [ ] D2: README section written, committed, pushed, Baldwin told
- [ ] E (optional): rover runs the route; clip filmed
