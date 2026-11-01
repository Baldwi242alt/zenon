"""Visible fraction of the Sun's disk above the terrain horizon.

At the lunar south pole the Sun sits within about 1.5 degrees of the
horizon, and its disk is about 0.53 degrees wide. So "is the Sun up?" is
often the wrong question: a ridge can hide the bottom half of the disk.

We model the Sun as a circle of angular radius r, and the terrain horizon
as a straight horizontal line across it (the disk is so small that the
horizon barely changes across its width). The visible part is then a
circular segment, whose area has a closed-form formula.

Simplification (stated honestly): the horizon is treated as flat across
the disk's 0.53 degree width, and limb darkening (the Sun's edge being
dimmer than its centre) is ignored, so this is the visible *area* fraction.
"""

import numpy as np

from .constants import SUN_ANGULAR_RADIUS_DEG


def sun_visible_fraction(sun_elev_deg, horizon_deg, radius_deg=SUN_ANGULAR_RADIUS_DEG):
    """Fraction (0-1) of the Sun's disk above the terrain horizon.

    Works on single numbers or numpy arrays.

    d = how far the Sun's centre sits above the horizon, in degrees.
      d >= r  -> whole disk visible -> 1
      d <= -r -> whole disk hidden  -> 0
      between -> area of the circular segment above the line, divided by
                 the full disk area pi * r^2:
                 (r^2 * acos(-d/r) + d * sqrt(r^2 - d^2)) / (pi * r^2)

    Checks: d = 0 gives exactly 0.5 (half the disk), d = r gives 1, d = -r gives 0.
    """
    r = float(radius_deg)
    d = np.asarray(sun_elev_deg, dtype=float) - np.asarray(horizon_deg, dtype=float)
    # Clip so acos and sqrt stay defined; the clipped cases are handled by
    # the formula itself giving exactly 0 or 1 at the edges.
    dc = np.clip(d, -r, r)
    frac = (r * r * np.arccos(-dc / r) + dc * np.sqrt(r * r - dc * dc)) / (np.pi * r * r)
    # Fully clear or fully hidden disks get exact 1 and 0 (avoids 0.9999999).
    frac = np.where(d >= r, 1.0, np.where(d <= -r, 0.0, np.clip(frac, 0.0, 1.0)))
    return float(frac) if frac.ndim == 0 else frac
