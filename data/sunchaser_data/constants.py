"""Physical constants used across the Sunchaser data pipeline.

Every value here is a published figure, not a tuning knob.
"""

# Mean radius of the Moon in metres (IAU / NASA Moon fact sheet: 1,737.4 km).
MOON_RADIUS_M = 1_737_400.0

# Apparent angular radius of the Sun seen from 1 AU, in degrees.
# The solar disk is about 1,919 arcseconds across, so the radius is
# 959.6 arcsec = 0.2666 degrees. The Earth-Moon system stays near 1 AU
# from the Sun, so its distance changes this by only about 1.7%.
SUN_ANGULAR_RADIUS_DEG = 0.2666

# Mast height for the observer (rover panel / antenna) in metres.
# Project convention from the handbook (B.8), not a measured value.
DEFAULT_MAST_M = 2.0
