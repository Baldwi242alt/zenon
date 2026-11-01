"""Hand-checkable tests for picking a DSN complex."""

import numpy as np

from sunchaser_data.dsn import best_station


def test_best_station_picks_highest_moon_above_mask():
    els = {
        "Goldstone": np.array([30.0, 5.0, -20.0, 9.9]),
        "Madrid": np.array([12.0, 40.0, -5.0, -3.0]),
        "Canberra": np.array([-50.0, 11.0, 2.0, 9.0]),
    }
    # step 0: Goldstone highest; 1: Madrid; 2: nobody above 10 deg; 3: 9.9 is below the mask
    assert best_station(els) == ["Goldstone", "Madrid", None, None]
