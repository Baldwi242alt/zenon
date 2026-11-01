"""Sunchaser mission copilot: POST /api/copilot (schema 2.9). Owner: Baldwin.

Request:  {"question": "Which site gives the most usable days in March?", "site": "malapert_massif"}
          (site is optional)
Response: {"answer": "...", "facts_used": [{"label": "...", "value": "..."}]}

How it stays grounded
  1. Claude gets six TOOLS. Each one is plain Python that reads the computed
     files in shared/ (sites, scores, timelines, windows). Claude can't see the
     files directly; it has to ask the tools.
  2. Every tool returns its data plus a list of labelled FACTS.
  3. The NUMBERS GUARD checks every number in Claude's answer against the
     numbers the tools actually returned (allowing normal rounding). If one
     doesn't match, Claude gets one chance to fix it; if it still doesn't,
     the copilot returns the facts instead of an unverified answer.
  4. facts_used lists the facts whose values appear in the answer, so the
     website can show what the answer was built from.

Model: claude-opus-5-5 at low effort, with server-side refusal fallback on.
The tool loop is written by hand (not the SDK's tool runner) because we need
to keep every tool result to build facts_used and run the guard.

Deployment (Vercel, file-based Python function): needs the environment
variable ANTHROPIC_API_KEY; dependencies in the repo-root requirements.txt;
bundle limits in vercel.json. Without a key it answers 503.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from functools import lru_cache
from http.server import BaseHTTPRequestHandler
from pathlib import Path

MODEL = "claude-opus-5-5"
MAX_QUESTION_CHARS = 500
MAX_TOOL_ROUNDS = 6
RATE_LIMIT_PER_MIN = 10

SHARED = Path(__file__).resolve().parents[1] / "shared"
if not SHARED.exists():  # Vercel runs functions from the project root
    SHARED = Path.cwd() / "shared"

# ===================== data access =====================


@lru_cache(maxsize=None)
def load(name):
    return json.loads((SHARED / name).read_text())


def sites():
    return load("sites.json")


def site_ids():
    return [s["id"] for s in sites()]


def site_name(sid):
    return next(s["name"] for s in sites() if s["id"] == sid)


def check_site(sid):
    if sid not in site_ids():
        raise ValueError(f"unknown site '{sid}'. Valid ids: {', '.join(site_ids())}")


def fmt_time(iso):
    t = datetime.strptime(iso, "%Y-%m-%dT%H:%MZ")
    return f"{t.day} {t.strftime('%b %Y %H:%M')} UTC"


def fact(label, value, unit=""):
    v = f"{value:g}" if isinstance(value, float) else str(value)
    return {"label": label, "value": f"{v}{(' ' + unit) if unit else ''}"}


# ===================== tools =====================


def tool_list_sites():
    s = load("scores.json")
    rank = {r["site"]: r["rank"] for r in s["sites"]}
    data = [{"id": x["id"], "name": x["name"], "lat": x["lat"], "lon": x["lon"],
             "elevation_m": x["elevation_m"], "scores_rank": rank.get(x["id"])} for x in sites()]
    return {"sites": data, "scores_window": f"{s['window_start']} to {s['window_end']}"}, \
        [fact(f"{x['name']} rank ({s['window_start'][:7]})", rank[x["id"]]) for x in sites()]


def tool_get_site_summary(site):
    check_site(site)
    s = load("scores.json")
    row = next(r for r in s["sites"] if r["site"] == site)
    meta = next(x for x in sites() if x["id"] == site)
    tl = load(f"timeline_{site}.json")["rows"]
    lit = sum(r["sun_frac"] >= 0.5 for r in tl) / len(tl) * 100
    earth = sum(r["earth_visible"] for r in tl) / len(tl) * 100
    name = meta["name"]
    data = {"site": meta, "scores_window": f"{s['window_start']} to {s['window_end']}", "score": row,
            "year_2027": {"sunlit_pct": round(lit, 1), "earth_visible_pct": round(earth, 1)}}
    facts = [fact(f"{name} rank, {s['window_start'][:7]}", row["rank"]),
             fact(f"{name} best landing", fmt_time(row["best_landing"])),
             fact(f"{name} usable days (best landing)", row["usable_days"]),
             fact(f"{name} longest dark spell (best landing)", row["longest_dark_h"], "h"),
             fact(f"{name} sunlit share of 2027", round(lit, 1), "%"),
             fact(f"{name} Earth in view, share of 2027", round(earth, 1), "%")]
    return data, facts


def _month_rows(site, month):
    if not re.fullmatch(r"2027-(0[1-9]|1[0-2])", month):
        raise ValueError("month must look like 2027-03 (data covers 2027)")
    return [r for r in load(f"windows_{site}.json")["rows"] if r["landing"].startswith(month)]


def _best(rows):
    return min(rows, key=lambda r: (not r["survives"], -r["usable_days"], r["longest_dark_h"], -r["contact_hours"]))


def tool_find_windows(site, month, min_usable_days):
    check_site(site)
    rows = [r for r in _month_rows(site, month) if r["usable_days"] >= min_usable_days]
    rows.sort(key=lambda r: (not r["survives"], -r["usable_days"], r["longest_dark_h"]))
    name = site_name(site)
    w = load(f"windows_{site}.json")
    data = {"site": site, "month": month, "mission_days": w["mission_days"], "matching_landings": len(rows),
            "survivable_matching": sum(r["survives"] for r in rows), "top": rows[:8]}
    facts = [fact(f"{name} landings in {month} with at least {min_usable_days:g} usable days", len(rows))]
    if rows:
        b = rows[0]
        facts += [fact(f"{name} best landing in {month}", fmt_time(b["landing"])),
                  fact(f"{name} usable days, best {month} landing", b["usable_days"]),
                  fact(f"{name} longest dark spell, best {month} landing", b["longest_dark_h"], "h")]
    return data, facts


def tool_compare_sites(month, site_list):
    ids = site_list or site_ids()
    for s in ids:
        check_site(s)
    table, facts = [], []
    for sid in ids:
        b = _best(_month_rows(sid, month))
        table.append({"site": sid, "name": site_name(sid), **b})
    table.sort(key=lambda r: (not r["survives"], -r["usable_days"], r["longest_dark_h"]))
    for i, r in enumerate(table, 1):
        r["rank_in_comparison"] = i
        facts.append(fact(f"{r['name']} usable days, best {month} landing", r["usable_days"]))
        facts.append(fact(f"{r['name']} survives best {month} landing", "yes" if r["survives"] else "no"))
    return {"month": month, "ranked": table}, facts


def tool_timeline_stats(site, start_date, end_date):
    check_site(site)
    rows = [r for r in load(f"timeline_{site}.json")["rows"] if start_date <= r["time"][:10] <= end_date]
    if not rows:
        raise ValueError("no timeline rows in that range (data covers 2027-01-01 to 2027-12-31)")

    def longest(flags):
        best = cur = 0
        for f in flags:
            cur = cur + 1 if f else 0
            best = max(best, cur)
        return best

    lit = [r["sun_frac"] >= 0.5 for r in rows]
    earth = [r["earth_visible"] for r in rows]
    n = len(rows)
    name = site_name(site)
    data = {"site": site, "from": start_date, "to": end_date, "hours": n,
            "sunlit_pct": round(100 * sum(lit) / n, 1), "earth_visible_pct": round(100 * sum(earth) / n, 1),
            "both_pct": round(100 * sum(a and b for a, b in zip(lit, earth)) / n, 1),
            "longest_dark_h": longest([not x for x in lit]), "longest_contact_gap_h": longest([not x for x in earth]),
            "dsn_link_pct": round(100 * sum(r["dsn_station"] is not None for r in rows) / n, 1)}
    span = f"{start_date} to {end_date}"
    facts = [fact(f"{name} sunlit, {span}", data["sunlit_pct"], "%"),
             fact(f"{name} Earth in view, {span}", data["earth_visible_pct"], "%"),
             fact(f"{name} longest dark spell, {span}", data["longest_dark_h"], "h"),
             fact(f"{name} longest contact gap, {span}", data["longest_contact_gap_h"], "h")]
    return data, facts


def tool_slip_cost(site, landing, budget):
    check_site(site)
    if budget <= 0:
        raise ValueError("budget must be positive")
    rows = load(f"windows_{site}.json")["rows"]
    times = [r["landing"] for r in rows]
    t = datetime.strptime(landing, "%Y-%m-%dT%H:%MZ") if "T" in landing else datetime.strptime(landing, "%Y-%m-%d")
    # Snap to the nearest landing time on or before the request (windows are every 6 h).
    idx = max((i for i, x in enumerate(times) if datetime.strptime(x, "%Y-%m-%dT%H:%MZ") <= t), default=0)
    step = load(f"windows_{site}.json")["step_h"]
    out, facts, name = [], [], site_name(site)
    for days in (0, 1, 2, 3, 7):
        j = idx + int(days * 24 / step)
        if j >= len(rows):
            break
        r = rows[j]
        cost = round(budget / r["usable_days"]) if r["usable_days"] else None
        out.append({"slip_days": days, "landing": r["landing"], "usable_days": r["usable_days"],
                    "survives": r["survives"], "cost_per_usable_day": cost})
        facts.append(fact(f"{name}: {days}-day slip, usable days", r["usable_days"]))
        facts.append(fact(f"{name}: {days}-day slip, cost per usable day",
                          cost if cost is not None else "no usable days"))
    return {"site": site, "requested_landing": landing, "budget": budget, "slips": out,
            "note": "Cost per usable day = budget / usable days; currency is whatever the budget is in."}, facts


TOOLS = {
    "list_sites": (tool_list_sites, "List the candidate landing sites (ids, names, positions, current rank).",
                   {}),
    "get_site_summary": (tool_get_site_summary,
                         "Scores and 2027 light/contact summary for one site.",
                         {"site": {"type": "string", "description": "site id from list_sites"}}),
    "find_windows": (tool_find_windows,
                     "Landing times at a site in a month (2027) with at least a number of usable days.",
                     {"site": {"type": "string"}, "month": {"type": "string", "description": "e.g. 2027-03"},
                      "min_usable_days": {"type": "number"}}),
    "compare_sites": (tool_compare_sites,
                      "Best landing per site in a month (2027), ranked; site_list empty means all sites.",
                      {"month": {"type": "string", "description": "e.g. 2027-03"},
                       "site_list": {"type": "array", "items": {"type": "string"}}}),
    "timeline_stats": (tool_timeline_stats,
                       "Sunlight and Earth-contact statistics at a site between two dates (inclusive, 2027).",
                       {"site": {"type": "string"}, "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "YYYY-MM-DD"}}),
    "slip_cost": (tool_slip_cost,
                  "Usable days and cost per usable day if a landing slips by 0, 1, 2, 3 or 7 days.",
                  {"site": {"type": "string"}, "landing": {"type": "string", "description": "2027-06-19T18:00Z"},
                   "budget": {"type": "number", "description": "mission budget, any currency"}}),
}


def tool_schemas():
    return [{"name": name, "description": desc, "strict": True,
             "input_schema": {"type": "object", "properties": props, "required": list(props),
                              "additionalProperties": False}}
            for name, (_, desc, props) in TOOLS.items()]


def run_tool(name, args):
    """Run one tool. Returns (json text for Claude, facts, is_error)."""
    try:
        data, facts = TOOLS[name][0](**args)
        return json.dumps({"data": data, "facts": facts}), facts, False
    except (KeyError, ValueError, TypeError, StopIteration) as exc:
        return json.dumps({"error": str(exc)}), [], True


# ===================== numbers guard =====================

NUMBER = re.compile(r"(?<![A-Za-z_])-?\d+(?:\.\d+)?")


def allowed_numbers(*texts):
    ok = set()
    for text in texts:
        for raw in NUMBER.findall(text.replace(",", "")):
            n = float(raw)
            ok.update({n, abs(n), round(n), round(n, 1), abs(round(n)), abs(round(n, 1))})
    return ok


def unsupported_numbers(answer, evidence_texts):
    ok = allowed_numbers(*evidence_texts)
    return [raw for raw in NUMBER.findall(answer.replace(",", "")) if float(raw) not in ok and abs(float(raw)) not in ok]


def facts_in_answer(answer, facts):
    nums = {float(x) for x in NUMBER.findall(answer.replace(",", ""))}
    used = [f for f in facts if any(float(x) in nums for x in NUMBER.findall(f["value"].replace(",", "")))]
    seen, out = set(), []
    for f in used or facts[:8]:
        key = (f["label"], f["value"])
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out[:12]


# ===================== the copilot loop =====================

SYSTEM = """You are Sunchaser's mission copilot for lunar south-pole landing planning.
Answer ONLY from the results of your tools; they read Sunchaser's computed data (JPL Horizons
ephemerides, LRO LOLA terrain, 9 NASA Artemis III candidate regions, year 2027, 10-day missions).
Rules:
- Call tools to get every number you use. Copy numbers exactly as the tools return them; do not
  compute new numbers (no differences, ratios or percentages of your own).
- If the data does not cover the question (other years, other sites, things not computed), say so.
- Answer in 2-4 plain sentences. Mention site names, not ids. No markdown.
Mission rules: a usable day has enough sunlight and Earth contact; a landing "survives" if no dark spell
is longer than the survivable limit."""


def text_of(response):
    return " ".join(b.text for b in response.content if b.type == "text").strip()


def ask_claude(client, messages):
    return client.beta.messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM, tools=tool_schemas(),
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        messages=messages,
    )


def answer_question(question, site=None, client=None):
    """Run the tool loop and the numbers guard. Returns the response dict."""
    prompt = question if not site else f"{question}\n(The user is looking at site id '{site}'.)"
    messages = [{"role": "user", "content": prompt}]
    evidence, facts = [question], []
    for attempt in range(2):
        for _ in range(MAX_TOOL_ROUNDS):
            response = ask_claude(client, messages)
            if response.stop_reason == "refusal":
                return {"answer": "Sorry, I can't help with that question.", "facts_used": []}
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            calls = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})
            if not calls:
                break
            results = []
            for call in calls:
                text, f, is_error = run_tool(call.name, call.input)
                evidence.append(text)
                facts.extend(f)
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": text,
                                **({"is_error": True} if is_error else {})})
            messages.append({"role": "user", "content": results})
        answer = text_of(response)
        bad = unsupported_numbers(answer, evidence)
        if answer and not bad:
            return {"answer": answer, "facts_used": facts_in_answer(answer, facts)}
        messages.append({"role": "user", "content":
                         f"Your answer used numbers not found in the tool results: {', '.join(bad) or 'none'}. "
                         "Rewrite it using only numbers copied exactly from the tool results."})
    return {"answer": "I couldn't produce an answer I could verify against the data, so here are the "
                      "facts I found instead.", "facts_used": facts[:12]}


# ===================== HTTP handler (Vercel) =====================

_hits = {}


def rate_limited(ip):
    now = time.time()
    recent = [t for t in _hits.get(ip, []) if now - t < 60]
    _hits[ip] = recent + [now]
    return len(recent) >= RATE_LIMIT_PER_MIN


def make_client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    return anthropic.Anthropic()


def handle(body, ip="local", client=None):
    """Validate a request body and answer it. Returns (status, response dict)."""
    try:
        req = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return 400, {"error": "body must be JSON"}
    q = req.get("question")
    site = req.get("site")
    if not isinstance(q, str) or not q.strip() or len(q) > MAX_QUESTION_CHARS:
        return 400, {"error": f"'question' must be a non-empty string of at most {MAX_QUESTION_CHARS} characters"}
    if site is not None and site not in site_ids():
        return 400, {"error": f"unknown site '{site}'"}
    if rate_limited(ip):
        return 429, {"error": "too many questions; try again in a minute"}
    client = client or make_client()
    if client is None:
        return 503, {"error": "copilot not configured (ANTHROPIC_API_KEY missing)"}
    import anthropic
    try:
        return 200, answer_question(q.strip(), site, client)
    except anthropic.RateLimitError:
        return 429, {"error": "the AI service is busy; try again shortly"}
    except anthropic.APIStatusError as exc:
        return 502, {"error": f"AI service error ({exc.status_code})"}
    except anthropic.APIConnectionError:
        return 502, {"error": "could not reach the AI service"}


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        ip = (self.headers.get("x-forwarded-for") or self.client_address[0]).split(",")[0].strip()
        status, payload = handle(self.rfile.read(length), ip)
        self._send(status, payload)

    def do_GET(self):
        self._send(405, {"error": "use POST with {\"question\": \"...\"}"})
