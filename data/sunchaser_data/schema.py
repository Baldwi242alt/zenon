"""Checks that the shared files match the data contract (CLAUDE.md Section 2).

Every file Baldwin writes to shared/ goes through these checks first, so
a typo in a field name is caught here instead of breaking Dhiran's
website or Harril's planner.

Each check returns a list of problems (empty list = file is valid).
"""

import re

ISO_HOUR = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _check_fields(obj, spec, where, errors):
    """spec maps field name -> checker function returning True if valid."""
    if not isinstance(obj, dict):
        errors.append(f"{where}: expected an object")
        return
    for name, ok in spec.items():
        if name not in obj:
            errors.append(f"{where}: missing field '{name}'")
        elif not ok(obj[name]):
            errors.append(f"{where}.{name}: bad value {obj[name]!r}")
    for name in obj:
        if name not in spec:
            errors.append(f"{where}: unexpected field '{name}' (schema changes must be agreed)")


def check_sites(data):
    """Schema 2.1: a list of site objects."""
    errors = []
    if not isinstance(data, list) or not data:
        return ["sites: expected a non-empty list"]
    spec = {
        "id": lambda v: isinstance(v, str) and re.fullmatch(r"[a-z0-9_]+", v) is not None,
        "name": lambda v: isinstance(v, str) and v != "",
        "lat": lambda v: _is_num(v) and -90 <= v <= 90,
        "lon": lambda v: _is_num(v) and -180 <= v <= 360,
        "elevation_m": _is_num,
        "source": lambda v: isinstance(v, str),
        "notes": lambda v: isinstance(v, str),
    }
    for i, site in enumerate(data):
        _check_fields(site, spec, f"sites[{i}]", errors)
    ids = [s.get("id") for s in data if isinstance(s, dict)]
    if len(ids) != len(set(ids)):
        errors.append("sites: duplicate ids")
    return errors


def check_timeline(data):
    """Schema 2.2: hourly Sun/Earth rows for one site."""
    errors = []
    _check_fields(
        data,
        {
            "site": lambda v: isinstance(v, str),
            "start": lambda v: isinstance(v, str) and ISO_HOUR.match(v) is not None,
            "step_h": lambda v: _is_num(v) and v > 0,
            "rows": lambda v: isinstance(v, list) and len(v) > 0,
        },
        "timeline",
        errors,
    )
    if errors:
        return errors
    row_spec = {
        "time": lambda v: isinstance(v, str) and ISO_HOUR.match(v) is not None,
        "sun_elev_deg": _is_num,
        "sun_az_deg": lambda v: _is_num(v) and 0 <= v < 360,
        "sun_horizon_deg": _is_num,
        "sun_frac": lambda v: _is_num(v) and 0 <= v <= 1,
        "earth_elev_deg": _is_num,
        "earth_az_deg": lambda v: _is_num(v) and 0 <= v < 360,
        "earth_horizon_deg": _is_num,
        "earth_visible": lambda v: isinstance(v, bool),
        "dsn_station": lambda v: v is None or v in ("Goldstone", "Madrid", "Canberra"),
        "surface_temp_k": lambda v: v is None or (_is_num(v) and v > 0),
    }
    for i, row in enumerate(data["rows"]):
        _check_fields(row, row_spec, f"timeline.rows[{i}]", errors)
        if len(errors) > 20:
            errors.append("timeline: too many errors, stopping")
            break
    if data["rows"] and data["rows"][0].get("time") != data["start"]:
        errors.append("timeline: first row time must equal 'start'")
    return errors


def check_grid(data):
    """Schema 2.3: local terrain and per-cell sunlight around one site."""
    errors = []
    _check_fields(
        data,
        {
            "site": lambda v: isinstance(v, str),
            "window_start": lambda v: isinstance(v, str) and ISO_HOUR.match(v) is not None,
            "step_h": lambda v: _is_num(v) and v > 0,
            "n_steps": lambda v: isinstance(v, int) and v > 0,
            "rows": lambda v: isinstance(v, int) and v > 0,
            "cols": lambda v: isinstance(v, int) and v > 0,
            "cell_size_m": lambda v: _is_num(v) and v > 0,
            "center": lambda v: isinstance(v, dict) and _is_num(v.get("lat")) and _is_num(v.get("lon")),
            "orientation_note": lambda v: isinstance(v, str),
            "elevation_m": lambda v: isinstance(v, list),
            "slope_deg": lambda v: isinstance(v, list),
            "sun_pct": lambda v: isinstance(v, list),
        },
        "grid",
        errors,
    )
    if errors:
        return errors
    R, C, N = data["rows"], data["cols"], data["n_steps"]
    for name in ("elevation_m", "slope_deg"):
        arr = data[name]
        if len(arr) != R or any(len(r) != C for r in arr):
            errors.append(f"grid.{name}: expected {R} x {C}")
    sp = data["sun_pct"]
    if len(sp) != N:
        errors.append(f"grid.sun_pct: expected {N} steps, got {len(sp)}")
    for s, step in enumerate(sp):
        if len(step) != R or any(len(r) != C for r in step):
            errors.append(f"grid.sun_pct[{s}]: expected {R} x {C}")
            break
        if any((not isinstance(v, int)) or v < 0 or v > 100 for r in step for v in r):
            errors.append(f"grid.sun_pct[{s}]: values must be integers 0-100")
            break
    return errors


def check_windows(data):
    """Schema 2.4: every landing time across the year, scored."""
    errors = []
    _check_fields(
        data,
        {
            "site": lambda v: isinstance(v, str),
            "mission_days": lambda v: _is_num(v) and v > 0,
            "step_h": lambda v: _is_num(v) and v > 0,
            "rows": lambda v: isinstance(v, list) and len(v) > 0,
        },
        "windows",
        errors,
    )
    if errors:
        return errors
    row_spec = {
        "landing": lambda v: isinstance(v, str) and ISO_HOUR.match(v) is not None,
        "usable_days": lambda v: _is_num(v) and v >= 0,
        "sun_hours": lambda v: _is_num(v) and v >= 0,
        "contact_hours": lambda v: _is_num(v) and v >= 0,
        "both_hours": lambda v: _is_num(v) and v >= 0,
        "longest_dark_h": lambda v: _is_num(v) and v >= 0,
        "survives": lambda v: isinstance(v, bool),
    }
    for i, row in enumerate(data["rows"]):
        _check_fields(row, row_spec, f"windows.rows[{i}]", errors)
        if len(errors) > 20:
            break
    return errors


def check_scores(data):
    """Schema 2.5: ranked site summary for one window (usually a month)."""
    errors = []
    _check_fields(
        data,
        {
            "generated": lambda v: isinstance(v, str) and ISO_HOUR.match(v) is not None,
            "window_start": lambda v: isinstance(v, str) and ISO_DATE.match(v) is not None,
            "window_end": lambda v: isinstance(v, str) and ISO_DATE.match(v) is not None,
            "sites": lambda v: isinstance(v, list) and len(v) > 0,
        },
        "scores",
        errors,
    )
    if errors:
        return errors
    row_spec = {
        "site": lambda v: isinstance(v, str),
        "rank": lambda v: isinstance(v, int) and v >= 1,
        "usable_days": lambda v: _is_num(v) and v >= 0,
        "sun_hours": lambda v: _is_num(v) and v >= 0,
        "contact_hours": lambda v: _is_num(v) and v >= 0,
        "both_hours": lambda v: _is_num(v) and v >= 0,
        "longest_dark_h": lambda v: _is_num(v) and v >= 0,
        "survives": lambda v: isinstance(v, bool),
        "best_landing": lambda v: isinstance(v, str) and ISO_HOUR.match(v) is not None,
        "brief": lambda v: isinstance(v, str),
    }
    for i, row in enumerate(data["sites"]):
        _check_fields(row, row_spec, f"scores.sites[{i}]", errors)
    ranks = sorted(r.get("rank") for r in data["sites"] if isinstance(r, dict))
    if ranks != list(range(1, len(ranks) + 1)):
        errors.append("scores: ranks must be 1..N with no gaps")
    return errors
