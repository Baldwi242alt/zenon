"""Mission metrics computed from hourly timeline rows.

These are the numbers that end up in windows_SITE.json and scores.json:
usable days, sun hours, contact hours, longest dark spell, survives.

Definitions (CLAUDE.md 2.7):
  - An hour is "sunlit" when sun_frac >= 0.5 (at least half the disk visible).
  - An hour has "contact" when earth_visible is true.
  - A usable day is a 24-hour block with at least min_sun_hours sunlit hours
    AND at least min_contact_hours contact hours.
  - longest_dark_h is the longest unbroken run of non-sunlit hours.
  - survives is true when longest_dark_h <= max_dark_spell_hours.
"""

import numpy as np

SUNLIT_THRESHOLD = 0.5

# Placeholder criteria copied from the schema example in CLAUDE.md 2.7.
# Dhiran owns shared/criteria.json; once it exists, load that instead.
PLACEHOLDER_CRITERIA = {
    "mission_length_days": 10,
    "usable_day": {"min_sun_hours": 12, "min_contact_hours": 4},
    "max_dark_spell_hours": 18,
    "min_battery_reserve_pct": 15,
    "min_survival_probability": 0.95,
}


def longest_run(flags):
    """Length of the longest unbroken run of True values.

    Example: [T, T, F, T, T, T, F] -> 3.
    Walks the array once, counting the current run and remembering the best.
    """
    best = current = 0
    for f in flags:
        current = current + 1 if f else 0
        best = max(best, current)
    return best


def window_metrics(sun_frac, earth_visible, criteria, step_h=1):
    """Score one stretch of hourly data (for example, a 10-day mission).

    sun_frac       sequence of 0-1 values, one per step
    earth_visible  sequence of booleans, one per step
    criteria       dict in the criteria.json shape
    step_h         hours per step (1 for timelines)

    Only complete 24-hour days count towards usable_days; a trailing
    partial day is ignored.
    """
    sun = np.asarray(sun_frac, dtype=float) >= SUNLIT_THRESHOLD
    earth = np.asarray(earth_visible, dtype=bool)
    both = sun & earth

    steps_per_day = int(round(24 / step_h))
    n_days = len(sun) // steps_per_day
    min_sun = criteria["usable_day"]["min_sun_hours"]
    min_contact = criteria["usable_day"]["min_contact_hours"]

    usable = 0
    for d in range(n_days):
        day = slice(d * steps_per_day, (d + 1) * steps_per_day)
        if sun[day].sum() * step_h >= min_sun and earth[day].sum() * step_h >= min_contact:
            usable += 1

    longest_dark_h = longest_run(~sun) * step_h
    return {
        "usable_days": float(usable),
        "sun_hours": float(sun.sum() * step_h),
        "contact_hours": float(earth.sum() * step_h),
        "both_hours": float(both.sum() * step_h),
        "longest_dark_h": float(longest_dark_h),
        "survives": bool(longest_dark_h <= criteria["max_dark_spell_hours"]),
    }
