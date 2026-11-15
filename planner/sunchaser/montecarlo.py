"""Monte Carlo survival probability: how often does this route survive in practice?

Real hardware never matches its spec sheet exactly. So instead of saying a
route "survives", we replay it many times (500 by default) with a rover that is
slightly different each time, and report the share of runs that never freeze.

Each run multiplies:
  - battery capacity by a random factor  ~ normal(1, uncertainty_pct.battery_capacity / 100)
  - solar panel output by                ~ normal(1, uncertainty_pct.panel_output / 100)
  - every power draw by                  ~ normal(1, uncertainty_pct.power_draw / 100)
(each clipped to 0.5-1.5), and delays departure by a random 0-2 hours, so the
shadows are not quite where the plan expected them.

The random seed is fixed, so the same route always gets the same answer:
anyone can re-run the code and reproduce the number we publish.
"""

import numpy as np

from .sim import simulate


def survival_probability(world, plan, depart_step, n=500, seed=42, max_delay_h=2.0):
    """Returns {"survival_probability": 0-1, "p5_min_battery_pct": float, "runs": n}.

    p5_min_battery_pct is the 5th percentile of the lowest battery level reached:
    in 95% of runs the battery stayed above this.
    """
    unc = world.rover.get("uncertainty_pct", {})
    rng = np.random.default_rng(seed)
    cap = np.clip(rng.normal(1.0, unc.get("battery_capacity", 0) / 100.0, n), 0.5, 1.5)
    panel = np.clip(rng.normal(1.0, unc.get("panel_output", 0) / 100.0, n), 0.5, 1.5)
    draw = np.clip(rng.normal(1.0, unc.get("power_draw", 0) / 100.0, n), 0.5, 1.5)
    delay = rng.uniform(0.0, max_delay_h, n)
    survived = 0
    lows = []
    for i in range(n):
        r = simulate(world, plan, depart_step, delay_h=float(delay[i]), cap_scale=float(cap[i]),
                     panel_scale=float(panel[i]), draw_scale=float(draw[i]), log=False)
        survived += r["survived"]
        lows.append(r["min_battery_pct"])
    return {"survival_probability": survived / n,
            "p5_min_battery_pct": float(np.percentile(lows, 5)),
            "runs": n}
