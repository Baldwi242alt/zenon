"""Deep Space Network (DSN) coverage: which Earth complex can see the Moon.

Direct-to-Earth contact needs two things at once:
  1. Earth above the terrain horizon at the lunar site (timeline earth_visible);
  2. at least one DSN complex on Earth with the Moon above its antenna's
     elevation mask, so a dish can point at it.

NASA's three DSN complexes are spread roughly 120 degrees apart in longitude
so that one of them can almost always see any spacecraft. For each complex
we ask JPL Horizons for the Moon's elevation every hour (observer on Earth,
COMMAND='301'), and call the complex available when the Moon is above
10 degrees (the mask used in the handbook, B.10).

Coordinates are the complexes' approximate locations, to 0.01 degrees;
that is far more precise than needed, since moving a dish 1 km changes
the Moon's elevation there by about 0.01 degrees.

Simplification: the Moon's position is for the Moon's centre (a lunar
south-pole site is about 1,737 km from it, which shifts elevations seen from
Earth by up to about 0.3 degrees); dish scheduling and other missions
competing for antenna time are ignored.
"""

import numpy as np

from .horizons import MOON, az_el_series

ELEVATION_MASK_DEG = 10.0

# (name, east longitude deg, latitude deg, altitude km)
COMPLEXES = [
    ("Goldstone", -116.89, 35.43, 1.00),   # California, USA
    ("Madrid", -4.25, 40.43, 0.83),        # Robledo de Chavela, Spain
    ("Canberra", 148.98, -35.40, 0.68),    # Tidbinbilla, Australia
]


def moon_elevations(start, stop, step="1h"):
    """Moon elevation (deg) at each complex: {name: array}, plus the times."""
    out, times = {}, None
    for name, lon, lat, alt in COMPLEXES:
        t, _, el = az_el_series(MOON, lon, lat, alt, start, stop, step, center_body="399")
        if times is not None and t != times:
            raise ValueError("DSN time steps do not line up")
        times, out[name] = t, el
    return times, out


def best_station(elevations, mask=ELEVATION_MASK_DEG):
    """For each step, the complex with the Moon highest above the mask, or None.

    Picking the highest one is a simple stand-in for real scheduling: the
    Moon high in the sky means the best link margin there.
    """
    names = list(elevations)
    stack = np.vstack([elevations[n] for n in names])        # (complexes, steps)
    best = np.argmax(stack, axis=0)
    ok = stack.max(axis=0) > mask
    return [names[b] if o else None for b, o in zip(best, ok)]
