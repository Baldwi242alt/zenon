"""Surface temperature of the regolith, hour by hour (Insane tier, context only).

A 1D heat-conduction model of the top half-metre of lunar soil, using the
published regolith properties of Hayne et al. (2017, JGR Planets 122, 2371),
fitted to LRO Diviner temperature measurements, exactly as coded in Hayne's
open-source heat1d model (github.com/phayne/heat1d, python/heat1d/planets.py,
properties.py, profile.py):

  albedo A(i)   = 0.12 + 0.06 (i / 45 deg)^3 + 0.25 (i / 90 deg)^8   (i = solar incidence)
  emissivity    = 0.95;   geothermal heat flow Qb = 0.018 W/m^2
  density       rho(z) = 1800 - (1800 - 1100) exp(-z / 0.07 m)       (kg/m^3)
  conductivity  kc(z)  = 3.4e-3 - (3.4e-3 - 7.4e-4) exp(-z / 0.07 m) (W/m/K)
                k(T)   = kc (1 + 2.7 (T / 350 K)^3)                   (radiative part)
  heat capacity cp(T)  = 8.9093e-9 T^4 - 1.234e-5 T^3 + 2.3616e-3 T^2 + 2.7431 T - 3.6125

Each hour:
  1. Sunlight absorbed by the (tilted) surface:
       Qs = (1 - A(i)) * 1361 W/m^2 * max(cos i, 0) * sun_frac
     cos i uses the site's own slope and the direction it faces, from the
     LOLA 20 m DEM: the Sun is only ~1 deg up, so a slope tilted 10 deg
     towards it receives several times more heat than flat ground.
  2. Surface energy balance (no heat capacity at the very surface):
       emissivity * sigma * T0^4 = Qs + k (T1 - T0) / dz   (Newton's method)
  3. Heat diffuses through the soil layers (implicit finite differences, so
     1-hour steps are stable), with the geothermal flow at the bottom.
The year is run three times and the last run kept, so the soil "remembers"
the seasons instead of starting from an arbitrary temperature.

Honest limits: no heating from sunlight scattered off, or infrared emitted
by, surrounding terrain (so shadowed hours read colder than reality); one
slope per site (the 40 m around the point); Sun-Moon distance fixed at 1 AU
(about +/-3% in flux over a year). It's context for the planner, not a
substitute for Diviner measurements.
"""

import numpy as np

SIGMA = 5.670374419e-8      # Stefan-Boltzmann constant, W m^-2 K^-4
SOLAR = 1361.0              # W/m^2 at 1 AU
EMISSIVITY = 0.95
QB = 0.018                  # geothermal heat flow, W/m^2
A0, A_a, A_b = 0.12, 0.06, 0.25
KS, KD, RHOS, RHOD, H = 7.4e-4, 3.4e-3, 1100.0, 1800.0, 0.07
CHI = 2.7
CP_COEFF = [8.9093e-9, -1.234e-5, 2.3616e-3, 2.7431, -3.6125]


def albedo(incidence_rad):
    """Hayne et al. 2017 albedo, rising towards grazing incidence (capped at 1)."""
    i = np.asarray(incidence_rad, dtype=float)
    return np.minimum(A0 + A_a * (i / (np.pi / 4)) ** 3 + A_b * (i / (np.pi / 2)) ** 8, 1.0)


def heat_capacity(T):
    return np.polyval(CP_COEFF, T)


def depth_grid(dz0=0.002, growth=1.15, bottom=0.5):
    """Layer depths: 2 mm at the top, each layer 15% thicker, down to 0.5 m."""
    z, dz = [0.0], dz0
    while z[-1] < bottom:
        z.append(z[-1] + dz)
        dz *= growth
    return np.array(z)


def cos_incidence(sun_elev_deg, sun_az_deg, slope_deg=0.0, aspect_deg=0.0):
    """Cosine of the Sun's angle from the surface normal of a tilted surface.

    aspect = compass direction the slope faces (downhill), degrees from north.
    Flat ground: cos i = sin(elevation).
    """
    e, a = np.radians(sun_elev_deg), np.radians(sun_az_deg)
    s, asp = np.radians(slope_deg), np.radians(aspect_deg)
    return np.sin(e) * np.cos(s) + np.cos(e) * np.sin(s) * np.cos(a - asp)


def absorbed_flux(sun_elev_deg, sun_az_deg, sun_frac, slope_deg=0.0, aspect_deg=0.0):
    """Sunlight absorbed per square metre of surface, W/m^2."""
    ci = np.clip(cos_incidence(sun_elev_deg, sun_az_deg, slope_deg, aspect_deg), 0.0, 1.0)
    inc = np.arccos(ci)
    return (1.0 - albedo(inc)) * SOLAR * ci * np.asarray(sun_frac, dtype=float)


def surface_temperature(flux_w_m2, dt_s=3600.0, spinup_runs=2, T_init=None):
    """Surface temperature (K) for each step of absorbed flux.

    flux_w_m2: 1D array (one value per step) or 2D (sites, steps): several
    sites are solved together. The whole series is run spinup_runs extra
    times first so the deep soil reaches its seasonal state.
    """
    F = np.atleast_2d(np.asarray(flux_w_m2, dtype=float))
    n_sites, n_steps = F.shape
    z = depth_grid()
    N = len(z) - 1
    dzs = np.diff(z)                                     # layer gaps, length N
    rho = RHOD - (RHOD - RHOS) * np.exp(-z / H)
    kc = KD - (KD - KS) * np.exp(-z / H)
    if T_init is None:  # start near the long-term average radiative balance
        T_init = (np.maximum(F.mean(axis=1), 0.5) / (EMISSIVITY * SIGMA)) ** 0.25 * 0.9
    T = np.repeat(np.atleast_1d(T_init)[:, None], N + 1, axis=1).astype(float)
    out = np.empty((n_sites, n_steps))

    for run in range(spinup_runs + 1):
        for t in range(n_steps):
            k = kc[None, :] * (1.0 + CHI * (T / 350.0) ** 3)
            cp = heat_capacity(T)
            # 1. surface energy balance by Newton's method
            T0 = T[:, 0].copy()
            for _ in range(8):
                f = EMISSIVITY * SIGMA * T0 ** 4 - F[:, t] - k[:, 0] * (T[:, 1] - T0) / dzs[0]
                df = 4 * EMISSIVITY * SIGMA * T0 ** 3 + k[:, 0] / dzs[0]
                T0 = T0 - f / df
            # 2. implicit diffusion for layers 1..N-1 (Thomas algorithm)
            kp = 0.5 * (k[:, 1:N] + k[:, 2:N + 1])          # k between i and i+1
            km = 0.5 * (k[:, 0:N - 1] + k[:, 1:N])          # k between i-1 and i
            h = 0.5 * (dzs[1:N] + dzs[0:N - 1])             # control-volume width
            alpha = dt_s / (rho[None, 1:N] * cp[:, 1:N] * h[None, :])
            lo = -alpha * km / dzs[None, 0:N - 1]
            up = -alpha * kp / dzs[None, 1:N]
            di = 1.0 - lo - up
            rhs = T[:, 1:N].copy()
            rhs[:, 0] -= lo[:, 0] * T0                       # known surface temperature
            q = QB * dzs[-1] / k[:, N]                       # bottom: geothermal flux
            di[:, -1] += up[:, -1]
            rhs[:, -1] -= up[:, -1] * q
            m = N - 1
            cprime = np.empty((n_sites, m))
            dprime = np.empty((n_sites, m))
            cprime[:, 0] = up[:, 0] / di[:, 0]
            dprime[:, 0] = rhs[:, 0] / di[:, 0]
            for i in range(1, m):
                den = di[:, i] - lo[:, i] * cprime[:, i - 1]
                cprime[:, i] = up[:, i] / den
                dprime[:, i] = (rhs[:, i] - lo[:, i] * dprime[:, i - 1]) / den
            x = np.empty((n_sites, m))
            x[:, -1] = dprime[:, -1]
            for i in range(m - 2, -1, -1):
                x[:, i] = dprime[:, i] - cprime[:, i] * x[:, i + 1]
            T[:, 0] = T0
            T[:, 1:N] = x
            T[:, N] = T[:, N - 1] + q
            if run == spinup_runs:
                out[:, t] = T0
    return out[0] if np.ndim(flux_w_m2) == 1 else out


def site_slope_aspect(near_dem, lat, lon, half_width_m=40.0):
    """Slope (deg) and the compass direction it faces (deg from north) at a point.

    From a plane fitted to the LOLA DEM over +/-40 m around the point, turned
    into local north/east with the DEM's local north and east directions.
    """
    block, r0, c0 = near_dem.window(lat, lon, 4 * half_width_m)
    r, c = near_dem.latlon_to_rc(lat, lon)
    r, c = float(r) - r0, float(c) - c0
    k = half_width_m / near_dem.cell_size_m
    from .horizon import bilinear_sample
    h_up, h_dn = (bilinear_sample(block, np.array([r - k]), np.array([c]))[0],
                  bilinear_sample(block, np.array([r + k]), np.array([c]))[0])
    h_lf, h_rt = (bilinear_sample(block, np.array([r]), np.array([c - k]))[0],
                  bilinear_sample(block, np.array([r]), np.array([c + k]))[0])
    dh_drow = (h_dn - h_up) / (2 * half_width_m)        # per metre, moving down the map
    dh_dcol = (h_rt - h_lf) / (2 * half_width_m)        # per metre, moving right
    north, east = near_dem.local_north_east_rc(lat, lon)
    dh_dn = north[0] * dh_drow + north[1] * dh_dcol
    dh_de = east[0] * dh_drow + east[1] * dh_dcol
    slope = np.degrees(np.arctan(np.hypot(dh_dn, dh_de)))
    aspect = np.degrees(np.arctan2(-dh_de, -dh_dn)) % 360.0   # downhill direction
    return float(slope), float(aspect)
