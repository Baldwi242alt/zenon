"""Stage 7: shared/scores.json (ranked sites for one month) with AI briefs.

Run from the repo root:  python data/build_scores.py [--month 2027-MM]

1. For every month of 2027 and every site, score each landing time
   (every 6 hours) for a mission of criteria["mission_length_days"].
   The best landing is the one the rover survives with the most usable days
   (survival first, then usable days, shorter dark spell, more contact).
2. Pick the month with the biggest spread of best usable days between
   sites (the month where choosing the right site matters most), unless
   --month is given.
3. For that month: each site's best landing, its metrics, rank.
4. A three-sentence brief per site, by Claude (with the numbers guard) if an
   API key is configured, otherwise from the template.

Criteria come from shared/criteria.json (Dhiran) when it exists; until then
the placeholder values from CLAUDE.md 2.7 are used and the output says so.
"""

import argparse
import calendar
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

from sunchaser_data import schema  # noqa: E402
from sunchaser_data.briefs import generate_brief, get_client  # noqa: E402
from sunchaser_data.metrics import PLACEHOLDER_CRITERIA  # noqa: E402
from sunchaser_data.scores import best_landing, rank_sites, scan_landings  # noqa: E402

SHARED = ROOT / "shared"
META_OUT = ROOT / "data" / "sites" / "scores_meta.json"


def load_criteria():
    path = SHARED / "criteria.json"
    if path.exists():
        return json.loads(path.read_text()), "shared/criteria.json"
    return PLACEHOLDER_CRITERIA, "PLACEHOLDER criteria from CLAUDE.md 2.7 (shared/criteria.json not committed yet)"


def month_bounds(year, month):
    last_day = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-01T00:00Z", f"{year}-{month:02d}-{last_day:02d}T18:00Z", last_day


def nice_time(iso):
    t = datetime.strptime(iso, "%Y-%m-%dT%H:%MZ")
    return f"{t.day} {t.strftime('%b %Y, %H:%M')} UTC"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="force a month, e.g. 2027-03")
    args = ap.parse_args()

    criteria, crit_source = load_criteria()
    print(f"Criteria: {crit_source}")
    sites = json.loads((SHARED / "sites.json").read_text())
    rows = {s["id"]: json.loads((SHARED / f"timeline_{s['id']}.json").read_text())["rows"] for s in sites}

    # --- best landing per site for every month ---
    per_month = {}
    for month in range(1, 13):
        first, last, _ = month_bounds(2027, month)
        best = {}
        for s in sites:
            scored = scan_landings(rows[s["id"]], criteria, step_h=6, first=first, last=last)
            if scored:
                best[s["id"]] = best_landing(scored)
        if len(best) == len(sites):
            per_month[month] = best

    print("Month   spread  best usable days per site (sorted)")
    spreads = {}
    for month, best in per_month.items():
        days = [b["usable_days"] for b in best.values()]
        spreads[month] = statistics.pstdev(days)
        print(f"  {calendar.month_abbr[month]}   {spreads[month]:5.2f}   {sorted(days, reverse=True)}")

    if args.month:
        month = int(args.month.split("-")[1])
    else:
        month = max(spreads, key=lambda m: (spreads[m], -m))
    first, last, last_day = month_bounds(2027, month)
    window_name = f"{calendar.month_name[month]} 2027"
    print(f"Chosen window: {window_name} (spread {spreads[month]:.2f} days)")

    ranked = rank_sites(per_month[month])
    names = {s["id"]: s["name"] for s in sites}
    client = get_client()
    print("Briefs:", "Claude (" + "claude-opus-5-5" + ") with numbers guard" if client else
          "template (no ANTHROPIC_API_KEY set)")

    out_sites, sources = [], {}
    for rank, sid, m in ranked:
        facts = {
            "name": names[sid], "rank": rank, "n_sites": len(sites), "window": window_name,
            "best_landing": nice_time(m["landing"]), "mission_days": criteria["mission_length_days"],
            "mission_hours": criteria["mission_length_days"] * 24,
            "usable_days": m["usable_days"], "sun_hours": m["sun_hours"],
            "contact_hours": m["contact_hours"], "both_hours": m["both_hours"],
            "longest_dark_h": m["longest_dark_h"], "max_dark_h": criteria["max_dark_spell_hours"],
            "survives": m["survives"],
        }
        brief, source = generate_brief(facts, client)
        sources[sid] = source
        out_sites.append({
            "site": sid, "rank": rank, "usable_days": m["usable_days"], "sun_hours": m["sun_hours"],
            "contact_hours": m["contact_hours"], "both_hours": m["both_hours"],
            "longest_dark_h": m["longest_dark_h"], "survives": m["survives"],
            "best_landing": m["landing"], "brief": brief,
        })
        print(f"  {rank}. {names[sid]:22s} usable {m['usable_days']:4.0f}/{criteria['mission_length_days']} d  "
              f"dark max {m['longest_dark_h']:4.0f} h  survives {str(m['survives']):5s}  land {m['landing']}")

    scores = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "window_start": first[:10],
        "window_end": f"2027-{month:02d}-{last_day:02d}",
        "sites": out_sites,
    }
    errors = schema.check_scores(scores)
    if errors:
        raise SystemExit("scores.json fails the schema:\n  " + "\n  ".join(errors))
    (SHARED / "scores.json").write_text(json.dumps(scores, indent=2) + "\n")
    META_OUT.write_text(json.dumps({
        "criteria_source": crit_source, "criteria": criteria, "window": window_name,
        "month_spread_days": {calendar.month_abbr[k]: round(v, 2) for k, v in spreads.items()},
        "brief_source": sources,
    }, indent=2) + "\n")
    print(f"Wrote shared/scores.json (schema OK) and {META_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
