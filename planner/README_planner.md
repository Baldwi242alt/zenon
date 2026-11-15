# Sunchaser planner (owner: Harril)

Keeps a solar-powered rover alive at the Moon's south pole by planning **where to drive and when to
wait**, as the shadows move. Reads `shared/grid_SITE.json` (Baldwin) and `shared/rover.json` (Dhiran),
writes `shared/route_SITE.json` (schema 2.8 in `CLAUDE.md`).

```bash
python -m pytest planner/tests            # 27 tests, under a second
python planner/find_scenarios.py          # search 2027 for each site's demo scenario (needs the data cache)
python planner/run.py --all               # plan every route, write shared/route_*.json
python planner/run.py --site slater_plain --start 16,58 --target 5,5 --depart 24
```

> **Rover numbers are placeholders** until Dhiran commits `shared/rover.json`: the planner uses the handbook's
> example rover (`planner/fake/rover_fake.json`: 120 kg, 2,000 Wh battery, 0.6 m² panel at 30%, 200 m/h) and
> prints that it is doing so. Rerun `find_scenarios.py` and `run.py --all` when the real file lands.

## The rover model (`sunchaser/physics.py`)

| Quantity | Equation | With the placeholder rover |
| --- | --- | --- |
| Solar power in | 1361 W/m² × panel area × efficiency × (visible share of the Sun's disk) | up to 245 W |
| Power out, parked | avionics + heater (heater on when the Sun is under 5%) | 30 W lit, 90 W dark |
| Drive power | base + mass × 1.62 × speed × (rolling resistance × cos slope + sin slope) ÷ drivetrain efficiency | 43.2 W flat, 48.7 W up 15° |
| Battery | charge at 95% efficiency, discharge in full, capped at capacity, dead at zero | 2,000 Wh |

**The energy insight.** Driving on the flat costs 3.2 W of mechanical power and climbing a 15° slope costs
8.7 W, against 90 W just to stay alive in the dark. At walking pace on the Moon, heaters and electronics
dominate: **darkness, not slope, is the enemy.** A parked rover lasts 18.9 hours in the dark before it
reaches its 15% reserve and 22.2 hours before it is dead. So the planner's job is to avoid long darkness;
slope only matters as a safety limit (no moves steeper than the rover's limit).

The panel is vertical and tracks the Sun, and the Sun is within about 1.5° of the horizon, so the
cosine loss is under 0.04% and is ignored.

## One energy rule for everything (`sunchaser/world.py`)

`World.advance()` moves the battery forward in one cell. Sunlight is constant within each hour of the grid,
so time is split at hour boundaries and each piece is integrated exactly. A move spends its first half in
the cell it leaves and its second half in the cell it enters. **The simulator and the planner both call
this same function**, so a route the planner calls safe is safe when replayed, to the watt-hour.

A move is blocked when either cell is steeper than the rover's limit, or the slope along the move is.

## The two planners

**Shortest route (`astar2d.py`).** Ordinary A\* over cells, cost in metres, octile-distance heuristic (the
length of the best route on an empty 8-connected grid, so it never overestimates and A\* stays optimal).
It ignores the Sun. This is what a planner does if it only looks at the map.

**Sunchaser (`astar_st.py`).** A\* over *states*: (cell, time, battery energy). From each state the rover can
move to a neighbour, or wait (1 h or 0.5 h), charging if the cell is sunlit. Any action that would take the
battery below the reserve is discarded. The goal is the earliest arrival; the heuristic is the remaining
octile distance ÷ speed (the fastest conceivable arrival). Among routes that arrive at the same time, the one
with the most battery left is returned.

**Arriving safely.** Reaching the target only counts if the rover could then stay parked there for 24 hours
without breaching its reserve. Without this rule the planner happily "arrived" in the dark with 15% battery,
three hours from freezing. The Monte Carlo survival figure includes those 24 parked hours for every route.

**Why time and energy are in the state.** The same cell is a different place at a different hour (lit now,
dark later) and with a different battery (a full rover can cross a shadow that would kill a half-empty one).

**Dominance pruning.** That makes the state space explode, so each cell keeps only its *non-dominated* labels.
Label A dominates label B at a cell if A arrived no later than B and, **by simply waiting there until B's
arrival time, A would have at least as much energy as B** (checked with the real physics for that cell,
including charging and the reserve). Then anything B can do, A can do, and B is dropped. A wait step is by
definition "its parent, having waited", so labels remember which arrival they descend from and are never
compared with their own wait-chain. Waiting is only tried where it can matter: when the rover can charge,
or when sunlight in or next to the cell changes within 48 hours.

*Tiny example.* Two ways to reach the same sunlit cell: A at hour 3.0 with 1,500 Wh, B at hour 3.4 with
1,520 Wh. A, waiting 0.4 h in the Sun, gains 0.4 × 204 = 82 Wh and has 1,582 Wh at hour 3.4: more than B.
B is dominated and never expanded.

**Is the pruning safe?** `tests/test_spacetime.py` runs the planner with pruning off (brute force) on small
random worlds and checks the arrival time is identical. On the real Slater Plain grid a plan explores a few
thousand to a few hundred thousand labels instead of an unbounded number.

## Survival as a probability (`montecarlo.py`)

Hardware never matches its spec sheet. Each route is replayed **500 times** with battery capacity, panel
output and power draw each scaled by a random factor (normal, standard deviation from
`rover.uncertainty_pct`, 10% each for the placeholder, clipped to 0.5-1.5) and a random 0-2 hour departure
delay. `survival_probability` is the share of runs that never hit zero, on the way or in the 24 hours
parked at the destination afterwards. The random seed is fixed, so the
numbers are reproducible.

## Fast versus safe (`pareto.py`) and replanning (`replan.py`)

The trip is planned at three reserves: the rover's own (15%), 30% and 45%. The first is `sunchaser_fast`;
the one with the best survival odds is `sunchaser_safe`; all three go in the `pareto` list (time versus
survival probability) so a mission team can choose its risk level.

`replan.py` injects a fault part-way along the fast route (dust on the panel: output −30%) and compares
"carry on with the old plan" against "replan from here". Results are in `planner/out/replan_SITE.json`.

## How the demo scenarios were chosen (`find_scenarios.py`)

Nothing is staged. For each site the whole of 2027 is searched: start/target pairs at least 3.8 km apart on
gentle ground, a departure every 12 hours, keeping cases where the rover starts in sunlight and the shortest
route freezes; the most promising are planned with Sunchaser and scored by the gap in survival probability.
The chosen window, start, target and departure are in `planner/scenarios.json`, and Baldwin's pipeline writes
`shared/grid_SITE.json` for exactly that window.

The grid is 5.1 km across (80 m cells) because on a 2.56 km grid no crossing takes longer than about 15 hours,
and the rover survives about 22 hours of darkness: nothing could ever fail. We changed the area, not the rover.

## What is simplified

- No wheel slip or sinkage; rolling resistance is one number.
- The heater is on or off (dark or lit), not a function of temperature.
- The rover starts with a full battery and does not transmit while driving (no comms power).
- 8-connected grid of 80 m cells: turns are 45° steps and features under 80 m are averaged out.
- Waits come in 1 h and 0.5 h steps, so "fastest" means fastest among routes built from those steps.
- Sunlight is the same within a cell and within an hour.

## What would change to fly this

Terramechanics for the real wheels, a thermal model driving heater power, comms windows as a constraint
(drive only where Earth is visible, or budget for blackouts), replanning on board as measured power deviates
from the plan, finer terrain near the route (rocks and craters under 80 m), and uncertainty in the terrain
model itself in the Monte Carlo runs.
