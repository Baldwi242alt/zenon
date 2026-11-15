"""Tests for the JPL Horizons client.

The parser test uses a real Horizons response saved in fixtures/, so it
runs offline. The live test is skipped unless SUNCHASER_LIVE=1.
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from sunchaser_data import horizons

FIXTURE = Path(__file__).parent / "fixtures" / "horizons_earth_sample.json"


def test_parse_real_horizons_output():
    text = json.loads(FIXTURE.read_text())["result"]
    times, az, el = horizons.parse_az_el(text)
    assert times == ["2027-02-01T00:00Z", "2027-02-01T01:00Z",
                     "2027-02-01T02:00Z", "2027-02-01T03:00Z"]
    assert az[0] == pytest.approx(227.372982)
    assert el[0] == pytest.approx(-7.068270)


def test_parse_rejects_output_without_data():
    with pytest.raises(horizons.HorizonsError):
        horizons.parse_az_el("no data here")


def test_params_normalise_west_longitude_and_quote_values():
    p = horizons.build_params("10", -45.0, -89.5, 1.2, "2027-01-01", "2027-01-02")
    assert p["SITE_COORD"] == "'315.000000,-89.500000,1.20000'"
    assert p["COMMAND"] == "'10'"
    assert p["CENTER"] == "'coord@301'"


@pytest.mark.skipif(os.environ.get("SUNCHASER_LIVE") != "1", reason="set SUNCHASER_LIVE=1 for network tests")
def test_live_sun_skims_horizon_at_pole():
    site = {"lat": -89.45, "lon": 137.3, "elevation_m": 1850}
    s = horizons.sun_earth_for_site(site, "2027-02-01 00:00", "2027-02-03 00:00")
    assert len(s["times"]) == 49
    assert np.all(np.abs(s["sun_elev_deg"]) < 2.2)
