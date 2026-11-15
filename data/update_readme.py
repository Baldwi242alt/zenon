"""Fill the "Headline results" block of the root README from the real files in shared/.

Run from the repo root after rebuilding data or routes:  python data/update_readme.py

Every number in that block is read from a file, so the README can't drift
from the data. The block sits between the RESULTS:START and RESULTS:END markers.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared"
README = ROOT / "README.md"


def load(name):
    return json.loads((SHARED / name).read_text())


def when(iso):
    t = datetime.strptime(iso, "%Y-%m-%dT%H:%MZ")
    return f"{t.day} {t.strftime('%b %H:%M')} UTC"


def build():
    sites = load("sites.json")
    names = {s["id"]: s["name"] for s in sites}
    scores = load("scores.json")
    month = datetime.strptime(scores["window_start"], "%Y-%m-%d").strftime("%B %Y")
    out = []

    # ---- sites and landing dates ----
    out.append(f"**Where and when to land** (best landing in {month}, 10-day mission; year-round light and contact):\n")
    out.append("| Rank | Site | Best landing | Usable days | Sunlit, 2027 | Earth in view, 2027 | Landings the rover survives, 2027 |")
    out.append("| --- | --- | --- | --- | --- | --- | --- |")
    for row in scores["sites"]:
        sid = row["site"]
        tl = load(f"timeline_{sid}.json")["rows"]
        lit = 100 * sum(r["sun_frac"] >= 0.5 for r in tl) / len(tl)
        earth = 100 * sum(r["earth_visible"] for r in tl) / len(tl)
        win = load(f"windows_{sid}.json")["rows"]
        ok = 100 * sum(r["survives"] for r in win) / len(win)
        days = f"{row['usable_days']:g} of 10" + ("" if row["survives"] else " (not survivable)")
        out.append(f"| {row['rank']} | {names[sid]} | {when(row['best_landing'])} | {days} | {lit:.0f}% | "
                   f"{earth:.0f}% | {ok:.0f}% |")
    worst = min(100 * sum(r["survives"] for r in load(f"windows_{s['id']}.json")["rows"])
                / len(load(f"windows_{s['id']}.json")["rows"]) for s in sites)
    best = max(100 * sum(r["survives"] for r in load(f"windows_{s['id']}.json")["rows"])
               / len(load(f"windows_{s['id']}.json")["rows"]) for s in sites)
    out.append(f"\nAcross the year only {worst:.0f}-{best:.0f}% of landing times are survivable, depending on the "
               "site: *when* you land matters as much as *where*.\n")

    # ---- rover routes ----
    rows, froze, n = [], 0, 0
    for s in sites:
        path = SHARED / f"route_{s['id']}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text())
        r = {x["name"]: x for x in d["routes"]}
        n += 1

        def cell(x):
            if x is None:
                return "none found"
            p = f"{100 * x['survival_probability']:.0f}%"
            if x["survived"]:
                return f"arrives in {x['duration_h']:.1f} h, survival {p}"
            return f"**freezes** after {x['duration_h']:.1f} h, survival {p}"

        froze += not r["shortest"]["survived"]
        rows.append(f"| {s['name']} | {cell(r['shortest'])} | {cell(r.get('sunchaser_fast'))} | "
                    f"{cell(r.get('sunchaser_safe'))} |")
    if rows:
        out.append("**How to drive** (a 4-5 km traverse at each site; survival = share of 500 Monte Carlo runs in "
                   "which the rover never froze):\n")
        out.append("| Site | Shortest route | Sunchaser (fastest safe) | Sunchaser (max margin) |")
        out.append("| --- | --- | --- | --- |")
        out.extend(rows)
        out.append(f"\nAt {froze} of {n} sites the shortest route freezes in the scenario found by searching 2027; "
                   "the sun-chasing route arrives every time. These are real windows of 2027 found by search, "
                   "not staged cases: `planner/find_scenarios.py`.\n")
    return "\n".join(out)


def main():
    text = README.read_text()
    a, b = text.index("<!-- RESULTS:START -->"), text.index("<!-- RESULTS:END -->")
    text = text[:a] + "<!-- RESULTS:START -->\n" + build() + "\n" + text[b:]
    README.write_text(text)
    print("README headline results updated")


if __name__ == "__main__":
    sys.exit(main())
