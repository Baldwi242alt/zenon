"""Laptop <-> rover bridge for the hardware-in-the-loop demo (owner: Harril).

What it does:
  1. Loads a planned route from shared/route_SITE.json (schema 2.8).
  2. Turns it into simple commands for the Arduino rover:
        F n     forward n cells      L deg / R deg   turn      W s   wait s seconds
  3. Sends them one at a time over USB serial and listens to the rover's
     "LIGHT <0-1023>" readings (ten per second).
  4. Maps light to sun_pct with two calibration numbers (reading when covered,
     reading under the lamp) and runs the SAME battery physics as the planner
     (planner/sunchaser/physics.py) in compressed time. The time scale is set
     so the physical rover keeps the plan's pace: one cell on the printed map
     takes as many simulated hours as one 80 m cell takes the planned rover.
  5. If the simulated battery falls below the reserve while the rover is in the
     light, it sends STOP so the rover parks and recharges, and GO once it has.
     (In the dark it keeps driving: stopping there only drains the battery.)

Run from the repo root:
    python hardware/bridge.py --site slater_plain --route sunchaser_fast --port COM5
    python hardware/bridge.py --site slater_plain --simulate          # no rover needed
    python hardware/bridge.py --site slater_plain --commands          # just print the commands

--simulate replaces the rover with a software stand-in whose "light sensor"
follows the sun_pct recorded in the route, so the whole loop can be tested and
demonstrated without hardware. Real serial needs `pip install pyserial`; the
live plot (--plot) needs matplotlib.

Honest status: the command conversion and battery loop are tested in software
(hardware/tests); the serial path has not been run against a physical rover yet.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "planner"))

from sunchaser import physics  # noqa: E402
from sunchaser.io import SHARED, load_rover  # noqa: E402

# Heading in degrees clockwise from "up the grid" (row decreasing) for each (d_row, d_col).
HEADINGS = {(-1, 0): 0, (-1, 1): 45, (0, 1): 90, (1, 1): 135, (1, 0): 180, (1, -1): 225, (0, -1): 270, (-1, -1): 315}


def route_to_commands(steps, start_heading=0, seconds_per_hour=1.0):
    """Turn schema-2.8 steps into rover commands.

    Consecutive moves in the same direction are merged into one F command; a
    diagonal cell counts as 1.41 cells. Waits become W with the wait's simulated
    hours converted to real seconds.
    Returns a list of command strings.
    """
    cmds = []
    heading = start_heading % 360
    run = 0.0                                   # cells accumulated in the current direction

    def flush():
        nonlocal run
        if run > 0:
            cmds.append(f"F {run:.2f}")
            run = 0.0

    for prev, step in zip(steps, steps[1:]):
        if step["action"] == "wait":
            flush()
            cmds.append(f"W {(step['t_h'] - prev['t_h']) * seconds_per_hour:.2f}")
            continue
        d = (step["row"] - prev["row"], step["col"] - prev["col"])
        if d not in HEADINGS:
            raise ValueError(f"step is not a move to a neighbouring cell: {prev} -> {step}")
        want = HEADINGS[d]
        turn = (want - heading + 180) % 360 - 180          # shortest turn, -180..180
        if turn:
            flush()
            cmds.append(f"R {turn}" if turn > 0 else f"L {-turn}")
            heading = want
        run += 1.41 if d[0] and d[1] else 1.0
    flush()
    return cmds


def seconds_per_sim_hour(steps, ms_per_cell):
    """Real seconds per simulated hour so that the physical rover keeps the plan's pace.

    The plan says how many simulated hours one straight cell takes (cell size / rover speed);
    the physical rover takes ms_per_cell to drive one cell on the printed map. Matching the
    two keeps the battery simulation in step with where the rover actually is.
    """
    for prev, step in zip(steps, steps[1:]):
        straight = (step["row"] == prev["row"]) != (step["col"] == prev["col"])
        if step["action"] == "move" and straight:
            return (ms_per_cell / 1000.0) / (step["t_h"] - prev["t_h"])
    return 1.0


def light_to_sun_pct(reading, dark_reading, lamp_reading):
    """Map a raw LDR reading (0-1023) to 0-100% using the two calibration readings."""
    if lamp_reading == dark_reading:
        return 0.0
    pct = 100.0 * (reading - dark_reading) / (lamp_reading - dark_reading)
    return max(0.0, min(100.0, pct))


class BatteryLoop:
    """The simulated battery, driven by light readings in compressed time."""

    def __init__(self, rover, seconds_per_hour=1.0):
        self.rover = rover
        self.seconds_per_hour = seconds_per_hour
        self.energy = float(rover["battery"]["capacity_wh"])
        self.reserve = rover["battery"]["min_soc"] * self.energy
        # Resume once comfortably above the reserve, so STOP/GO doesn't chatter.
        self.resume_at = min(self.energy, self.reserve * 2.0)
        self.paused = False
        self.frozen = False
        self.history = []                          # (simulated hours, energy Wh, sun_pct)
        self.sim_hours = 0.0

    def update(self, sun_pct, real_dt_s, driving):
        """Advance by real_dt_s seconds of real time. Returns "STOP", "GO" or None."""
        dt_h = real_dt_s / self.seconds_per_hour
        drive = physics.drive_w(self.rover, 0.0, 0.0, 1.0) if (driving and not self.paused) else 0.0
        p_in = physics.power_in_w(self.rover, sun_pct)
        p_out = physics.power_out_w(self.rover, sun_pct, drive)
        self.energy, frozen, breached = physics.battery_step(self.rover, self.energy, p_in, p_out, dt_h)
        self.energy = max(self.energy, 0.0)
        self.frozen = self.frozen or frozen
        self.sim_hours += dt_h
        self.history.append((self.sim_hours, self.energy, sun_pct))
        # Stopping only helps where the rover can charge. In the dark, a parked rover still
        # burns 90 W, so it keeps to the plan and drives on towards the light.
        if breached and not self.paused and p_in > p_out - drive:
            self.paused = True
            return "STOP"
        if self.paused and self.energy >= self.resume_at:
            self.paused = False
            return "GO"
        return None


class FakeRover:
    """Software stand-in for the Arduino: executes commands on a clock and reports light.

    Its light reading follows the sun_pct recorded along the route, so a
    simulated run reproduces the planned lighting.
    """

    MS_PER_CELL, MS_PER_45 = 1200, 260

    def __init__(self, steps, seconds_per_hour, dark_reading=80, lamp_reading=900):
        self.steps, self.sph = steps, seconds_per_hour
        self.dark, self.lamp = dark_reading, lamp_reading
        self.clock = 0.0            # real seconds
        self.paused_s = 0.0         # real seconds spent paused (the rover is not moving along the route)
        self.busy_until = 0.0
        self.paused = False
        self.moving = False
        self.out = []

    def write(self, cmd):
        if cmd == "STOP":
            self.paused = True
        elif cmd == "GO":
            self.paused = False
        else:
            kind, value = cmd[0], float(cmd[1:])
            secs = {"F": value * self.MS_PER_CELL / 1000, "W": value}.get(kind, value / 45 * self.MS_PER_45 / 1000)
            self.busy_until = self.clock + secs
            self.moving = kind == "F"

    def tick(self, dt):
        """Advance the clock; returns the lines the rover would print."""
        lines = []
        if self.paused:
            self.busy_until += dt
            self.paused_s += dt
        self.clock += dt
        sim_h = (self.clock - self.paused_s) / self.sph      # how far along the route the rover is
        pct = self.steps[0]["sun_pct"]
        for st in self.steps:
            if st["t_h"] <= sim_h:
                pct = st["sun_pct"]
        lines.append(f"LIGHT {int(self.dark + (self.lamp - self.dark) * pct / 100)}")
        if self.busy_until and self.clock >= self.busy_until and not self.paused:
            self.busy_until = 0.0
            self.moving = False
            lines.append("DONE")
        return lines


def run(route, rover, link, seconds_per_hour, dark_reading, lamp_reading, real_time=True, plot=False, log=print):
    """Drive the route. `link` needs write(cmd) and tick(dt) -> list of lines."""
    cmds = route_to_commands(route["steps"], seconds_per_hour=seconds_per_hour)
    loop = BatteryLoop(rover, seconds_per_hour)
    fig = None
    if plot:
        import matplotlib.pyplot as plt
        plt.ion()
        fig, ax = plt.subplots()
    dt = 0.1
    for i, cmd in enumerate(cmds):
        link.write(cmd)
        log(f"[{loop.sim_hours:6.1f} h] -> {cmd}   battery {loop.energy:6.0f} Wh")
        done = False
        while not done:
            for line in link.tick(dt):
                if line.startswith("LIGHT"):
                    pct = light_to_sun_pct(int(line.split()[1]), dark_reading, lamp_reading)
                    action = loop.update(pct, dt, driving=cmd.startswith("F"))
                    if action:
                        link.write(action)
                        log(f"[{loop.sim_hours:6.1f} h] battery {loop.energy:6.0f} Wh, light {pct:3.0f}% -> {action}")
                elif line == "DONE":
                    done = True
            if loop.frozen:
                log(f"[{loop.sim_hours:6.1f} h] battery empty: the rover froze")
                return loop
            if real_time:
                time.sleep(dt)
        if fig is not None and i % 3 == 0:
            ax.clear()
            ax.plot([h[0] for h in loop.history], [h[1] for h in loop.history])
            ax.axhline(loop.reserve, linestyle="--")
            ax.set_xlabel("simulated hours"); ax.set_ylabel("battery (Wh)")
            fig.canvas.draw(); fig.canvas.flush_events()
    log(f"[{loop.sim_hours:6.1f} h] route complete, battery {loop.energy:.0f} Wh")
    return loop


class SerialRover:
    """The real rover on a serial port."""

    def __init__(self, port, baud=115200):
        import serial
        self.ser = serial.Serial(port, baud, timeout=0.05)
        time.sleep(2.0)                      # the Uno resets when the port opens

    def write(self, cmd):
        self.ser.write((cmd + "\n").encode())

    def tick(self, dt):
        lines = []
        while self.ser.in_waiting:
            line = self.ser.readline().decode(errors="ignore").strip()
            if line:
                lines.append(line)
        return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--route", default="sunchaser_fast")
    ap.add_argument("--port")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--commands", action="store_true", help="print the command list and exit")
    ap.add_argument("--ms-per-cell", type=float, default=1200, help="same value as MS_PER_CELL in rover.ino")
    ap.add_argument("--seconds-per-hour", type=float,
                    help="real seconds per simulated hour (default: matched to the rover's pace)")
    ap.add_argument("--dark", type=int, default=80, help="LDR reading with the sensor covered")
    ap.add_argument("--lamp", type=int, default=900, help="LDR reading under the lamp")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--fast", action="store_true", help="with --simulate: don't sleep between ticks")
    args = ap.parse_args()

    data = json.loads((SHARED / f"route_{args.site}.json").read_text())
    route = next(r for r in data["routes"] if r["name"] == args.route)
    rover, source = load_rover()
    print(f"Rover: {source}")
    sph = args.seconds_per_hour or seconds_per_sim_hour(route["steps"], args.ms_per_cell)
    print(f"Time scale: {sph:.2f} real seconds per simulated hour")
    if args.commands:
        print("\n".join(route_to_commands(route["steps"], seconds_per_hour=sph)))
        return
    if args.simulate:
        link = FakeRover(route["steps"], sph, args.dark, args.lamp)
    elif args.port:
        link = SerialRover(args.port)
    else:
        ap.error("give --port, --simulate or --commands")
    run(route, rover, link, sph, args.dark, args.lamp,
        real_time=not (args.simulate and args.fast), plot=args.plot)


if __name__ == "__main__":
    main()
