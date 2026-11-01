"""Landing-time scoring: how good is it to land at a given hour?

A mission lands at time T and works for criteria["mission_length_days"]
days. We score it with metrics.window_metrics over the timeline rows from
T onwards: usable days, sun/contact hours, longest dark spell, survives.

scan_landings() scores every landing time on a fixed step (6 h by
default); Stage 7 uses it within one month for scores.json, and Stage 8
uses it across the whole year for windows_SITE.json.
"""

from datetime import datetime

from .metrics import window_metrics


def parse_time(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ")


def scan_landings(rows, criteria, step_h=6, first=None, last=None):
    """Score landing times every step_h hours.

    rows      timeline rows (hourly, schema 2.2)
    first/last  optional ISO times bounding the landing times (inclusive)
    Only landings whose whole mission fits inside the timeline are scored.
    Returns a list of dicts: {"landing": time, **metrics}.
    """
    mission_h = int(criteria["mission_length_days"] * 24)
    sun = [r["sun_frac"] for r in rows]
    earth = [r["earth_visible"] for r in rows]
    out = []
    for i in range(0, len(rows) - mission_h + 1, step_h):
        t = rows[i]["time"]
        if first and parse_time(t) < parse_time(first):
            continue
        if last and parse_time(t) > parse_time(last):
            break
        m = window_metrics(sun[i:i + mission_h], earth[i:i + mission_h], criteria)
        out.append({"landing": t, **m})
    return out


def _order_key(m):
    """Sort key, best first: survives, then usable days, then shorter dark, then more contact.

    Survival comes first (a team decision on top of handbook B.13, which ranks
    by usable days first): a rover that freezes in a long dark spell gets no
    more usable days, so a landing it survives beats one with more usable days
    on paper that it doesn't.
    """
    return (not m["survives"], -m["usable_days"], m["longest_dark_h"], -m["contact_hours"])


def best_landing(scored):
    """The best landing time in a list of scored landings (see _order_key)."""
    return min(scored, key=_order_key)


def rank_sites(best_by_site):
    """Order sites by their best landing (see _order_key).

    best_by_site: {site_id: best-landing dict}. Returns a list of (rank, site_id, dict).
    """
    order = sorted(best_by_site.items(), key=lambda kv: _order_key(kv[1]))
    return [(i + 1, sid, m) for i, (sid, m) in enumerate(order)]
