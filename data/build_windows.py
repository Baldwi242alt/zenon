"""Stage 8: shared/windows_SITE.json, every landing time across 2027, scored.

Run from the repo root:  python data/build_windows.py

For each site, a landing every 6 hours from 1 Jan 2027 until the last
landing whose whole mission still fits inside the 2027 timeline. Each row
scores a mission of criteria["mission_length_days"] starting at that time
(usable days, sun/contact/both hours, longest dark spell, survives), using
the same rules as scores.json. This feeds Dhiran's landing-window heatmap
and the cost-of-a-slip chart: compare a row with the rows 4, 8, 12 or 28
steps later to see what a 1, 2, 3 or 7-day slip costs.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

from build_scores import load_criteria  # noqa: E402
from sunchaser_data import schema  # noqa: E402
from sunchaser_data.scores import scan_landings  # noqa: E402

SHARED = ROOT / "shared"
STEP_H = 6


def main():
    criteria, source = load_criteria()
    print(f"Criteria: {source}")
    sites = json.loads((SHARED / "sites.json").read_text())
    for s in sites:
        rows = json.loads((SHARED / f"timeline_{s['id']}.json").read_text())["rows"]
        scored = scan_landings(rows, criteria, step_h=STEP_H)
        out = {
            "site": s["id"],
            "mission_days": criteria["mission_length_days"],
            "step_h": STEP_H,
            "rows": [{
                "landing": r["landing"], "usable_days": r["usable_days"], "sun_hours": r["sun_hours"],
                "contact_hours": r["contact_hours"], "both_hours": r["both_hours"],
                "longest_dark_h": r["longest_dark_h"], "survives": r["survives"],
            } for r in scored],
        }
        errors = schema.check_windows(out)
        if errors:
            raise SystemExit(f"windows_{s['id']} fails the schema:\n  " + "\n  ".join(errors[:10]))
        path = SHARED / f"windows_{s['id']}.json"
        path.write_text(json.dumps(out, separators=(",", ":")))
        ok = [r for r in scored if r["survives"]]
        full = [r for r in ok if r["usable_days"] == criteria["mission_length_days"]]
        print(f"  {path.name:34s} {len(scored)} landings  {path.stat().st_size / 1e3:4.0f} KB  "
              f"survivable {100 * len(ok) / len(scored):5.1f}%  all days usable {100 * len(full) / len(scored):5.1f}%")


if __name__ == "__main__":
    main()
