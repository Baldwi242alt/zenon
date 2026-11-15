"""Hand-checkable tests for the regolith temperature model."""

import numpy as np
import pytest

from sunchaser_data import thermal


def test_albedo_matches_hayne_formula():
    assert thermal.albedo(0.0) == pytest.approx(0.12)
    assert thermal.albedo(np.pi / 4) == pytest.approx(0.12 + 0.06 + 0.25 * 0.5 ** 8)


def test_incidence_flat_and_tilted():
    # Flat ground: cos i = sin(elevation).
    assert thermal.cos_incidence(30.0, 0.0) == pytest.approx(0.5)
    # Sun 1 deg up in the north; a 10 deg slope facing north sees it as if 11 deg up.
    assert thermal.cos_incidence(1.0, 0.0, 10.0, 0.0) == pytest.approx(np.sin(np.radians(11.0)))
    # Same slope facing away: the Sun is below the slope's own horizon.
    assert thermal.cos_incidence(1.0, 0.0, 10.0, 180.0) < 0


def test_steady_flux_reaches_radiative_balance():
    # Constant absorbed flux F for long enough: emissivity*sigma*T^4 = F + geothermal flux.
    F = 200.0
    T = thermal.surface_temperature(np.full(24 * 60, F), spinup_runs=3)
    expected = ((F + thermal.QB) / (thermal.EMISSIVITY * thermal.SIGMA)) ** 0.25
    assert T[-1] == pytest.approx(expected, rel=0.01)


def test_equator_day_night_matches_diviner():
    # Synthetic lunar equator: Sun passes overhead once per 29.53-day lunar day.
    # Diviner measured about 390 K at equatorial noon and about 95 K before dawn
    # (Williams et al. 2017; Hayne et al. 2017).
    hours = np.arange(int(29.53 * 24))
    hour_angle = 360.0 * hours / (29.53 * 24) - 180.0
    elev = 90.0 - np.abs(hour_angle)
    flux = thermal.absorbed_flux(elev, 90.0, (elev > 0).astype(float))
    T = thermal.surface_temperature(flux, spinup_runs=3)
    assert 370 < T.max() < 400
    assert 85 < T.min() < 110
