"""The world the rover drives in: one grid (schema 2.3) plus one rover (schema 2.6).

World turns the JSON into flat lists the planner can read quickly, works out
once which moves are allowed and what each costs, and owns the single function
that moves the battery forward in time (advance). The simulator and the planner
both call advance, so a route the planner calls safe is safe when replayed.

Time convention: `t_abs` is hours since the grid's window_start. Sunlight for
hour index s (sun_pct[s]) applies from s to s+1. Cells are numbered
idx = row * cols + col.
"""

import math

from . import physics

SQRT2 = math.sqrt(2.0)
DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


class World:
    def __init__(self, grid, rover):
        self.grid, self.rover = grid, rover
        self.rows, self.cols = grid["rows"], grid["cols"]
        self.cell = float(grid["cell_size_m"])
        self.n_steps = grid["n_steps"]
        self.sun = [[v for row in step for v in row] for step in grid["sun_pct"]]
        self.elev = [v for row in grid["elevation_m"] for v in row]
        self.slope = [v for row in grid["slope_deg"] for v in row]

        self.peak = physics.panel_peak_w(rover)
        self.avionics = rover["power_w"]["avionics"]
        self.heater_dark = rover["power_w"]["heater_dark"]
        self.heater_lit = rover["power_w"]["heater_lit"]
        self.cap = float(rover["battery"]["capacity_wh"])
        self.eff = rover["battery"]["charge_efficiency"]
        self.min_soc = rover["battery"]["min_soc"]
        self.speed = float(rover["drive"]["speed_m_per_h"])
        self.max_slope = rover["drive"]["max_slope_deg"]
        self.side_h = self.cell / self.speed          # hours to cross one cell
        self.diag_h = self.cell * SQRT2 / self.speed

        # Allowed moves from every cell: (neighbour idx, duration h, drive power W, distance m).
        # A move is blocked when either cell is steeper than the rover's limit, or the
        # slope along the move itself is (handbook 5.6).
        self.moves = [[] for _ in range(self.rows * self.cols)]
        for r in range(self.rows):
            for c in range(self.cols):
                a = r * self.cols + c
                if self.slope[a] > self.max_slope:
                    continue
                for dr, dc in DIRS:
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                        continue
                    b = nr * self.cols + nc
                    if self.slope[b] > self.max_slope:
                        continue
                    dist = self.cell * (SQRT2 if dr and dc else 1.0)
                    along = math.degrees(math.atan(abs(self.elev[b] - self.elev[a]) / dist))
                    if along > self.max_slope:
                        continue
                    drive = physics.drive_w(rover, self.elev[a], self.elev[b], dist)
                    self.moves[a].append((b, dist / self.speed, drive, dist))

    # ----- helpers -----

    def idx(self, row, col):
        return row * self.cols + col

    def rc(self, idx):
        return divmod(idx, self.cols)

    def drivable(self, row, col):
        """A cell the rover may stand on and leave (gentle enough, with at least one move)."""
        return bool(self.moves[self.idx(row, col)])

    def sun_at(self, idx, t_abs):
        s = int(t_abs)
        return self.sun[s if s < self.n_steps else self.n_steps - 1][idx]

    def powers(self, idx, t_abs, drive=0.0, panel_scale=1.0, draw_scale=1.0):
        """(sun_pct, power_in_w, power_out_w) at a cell at a moment."""
        pct = self.sun_at(idx, t_abs)
        p_in = self.peak * panel_scale * pct * 0.01
        p_out = (self.avionics + (self.heater_dark if pct < physics.DARK_THRESHOLD_PCT else self.heater_lit)
                 + drive) * draw_scale
        return pct, p_in, p_out

    def advance(self, idx, t_abs, dt, energy, drive=0.0, cap=None, panel_scale=1.0, draw_scale=1.0):
        """Battery after spending dt hours in one cell, starting at t_abs.

        Sunlight is constant within each hour, so the time is split at hour
        boundaries and each piece is integrated exactly at constant power
        (same rule as physics.battery_step).
        Returns (energy_wh, lowest_energy_wh, frozen_after_h or None), where
        frozen_after_h is how long into dt the battery hit zero.
        """
        if cap is None:
            cap = self.cap
        sun, n = self.sun, self.n_steps
        peak = self.peak * panel_scale * 0.01
        base = self.avionics + drive
        end = t_abs + dt
        t = t_abs
        lowest = energy
        while True:
            s = int(t)
            seg_end = s + 1.0 if s + 1.0 < end else end
            h = seg_end - t
            pct = sun[s if s < n else n - 1][idx]
            net = peak * pct - (base + (self.heater_dark if pct < 5 else self.heater_lit)) * draw_scale
            if net > 0:
                energy += net * self.eff * h
                if energy > cap:
                    energy = cap
            else:
                before = energy
                energy += net * h
                if energy < lowest:
                    lowest = energy
                if energy <= 0:
                    return 0.0, 0.0, (t - t_abs) + (before / -net if net < 0 else 0.0)
            t = seg_end
            if t >= end - 1e-12:
                return energy, lowest, None

    def move_energy(self, a, b, dur, drive, t_abs, energy, cap=None, panel_scale=1.0, draw_scale=1.0):
        """Battery after driving from cell a to neighbouring cell b.

        The rover spends the first half of the move in cell a and the second
        half in cell b, drawing drive power throughout.
        Returns (energy_wh, lowest_energy_wh, frozen_after_h or None).
        """
        half = dur / 2.0
        e, low, froze = self.advance(a, t_abs, half, energy, drive, cap, panel_scale, draw_scale)
        if froze is not None:
            return e, low, froze
        e, low2, froze = self.advance(b, t_abs + half, half, e, drive, cap, panel_scale, draw_scale)
        if froze is not None:
            return e, 0.0, half + froze
        return e, (low if low < low2 else low2), None

    def octile_m(self, a, b):
        """Shortest possible driving distance between two cells on an obstacle-free grid."""
        ar, ac = divmod(a, self.cols)
        br, bc = divmod(b, self.cols)
        dr, dc = abs(ar - br), abs(ac - bc)
        return self.cell * (max(dr, dc) + (SQRT2 - 1.0) * min(dr, dc))
