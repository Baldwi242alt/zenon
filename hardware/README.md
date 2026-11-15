# Hardware-in-the-loop rover (owner: Harril)

A small Arduino robot drives the planned route on a printed map while its light sensor feeds the **same
battery physics** the planner uses. Shine a desk lamp on it ("the Sun") and the battery on screen charges;
shade it and the battery drains; let it run low and the laptop tells it to stop and wait for light.

```bash
python hardware/bridge.py --site slater_plain --commands          # print the command list for a route
python hardware/bridge.py --site slater_plain --simulate --fast   # whole loop in software, no rover
python hardware/bridge.py --site slater_plain --port COM5 --plot  # the real rover (pip install pyserial matplotlib)
python -m pytest hardware/tests
```

| File | What it is |
| --- | --- |
| `rover/rover.ino` | Arduino Uno sketch: L298N motor driver (IN1-IN4 on 5, 6, 9, 10; ENA 3, ENB 11), LDR divider on A0. Commands `F n`, `L deg`, `R deg`, `W s`, `STOP`, `GO`; prints `LIGHT <0-1023>` ten times a second and `DONE` after each command. Non-blocking, so `STOP` always gets through. |
| `bridge.py` | Converts a schema-2.8 route into commands (merging straight runs, shortest turns, diagonals as 1.41 cells), streams them, maps light to `sun_pct` with two calibration readings, runs `physics.battery_step` in compressed time matched to the rover's pace, sends `STOP` below the reserve and `GO` once recharged. `--simulate` swaps the rover for a software stand-in. |
| `tests/test_bridge.py` | Command conversion, light mapping, the STOP/GO loop (STOP after 18.9 h of darkness, as the physics says), and a full simulated run of a real route. |

**Parts:** Arduino Uno (or compatible), 2WD robot car chassis with motors, L298N driver, battery pack for the
motors, light-dependent resistor + 10 kΩ resistor, USB cable.

**Calibration:** time one cell forward and one 45° turn on your floor and set `MS_PER_CELL` and
`MS_PER_45_DEG` at the top of the sketch; read the LDR covered and under the lamp and pass them as
`--dark` and `--lamp`.

**Status, honestly:** the sketch and the serial path have been written and reviewed but **not yet run on a
physical rover**; everything on the laptop side is tested in software through the simulator.
