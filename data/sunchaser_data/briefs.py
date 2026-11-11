"""AI mission briefs with a numbers guard (handbook B.14).

For each site we hand Claude the computed facts as JSON and ask for three
plain-English sentences for a mission manager. Claude must not invent
numbers, and we don't just trust it: the numbers guard pulls every number
out of the generated text and checks that each one appears in the facts
(allowing for normal rounding). If any number fails, we ask once more; if
that fails too, we fall back to a sentence template filled from the facts.

Which AI: Gemini's free tier when GEMINI_API_KEY is set (no cost), else
Claude when ANTHROPIC_API_KEY is set. No key? Then every brief comes from the
template, and scores_meta.json records that. The Methods page states: "AI text is checked so it can't invent
numbers."

API notes (Anthropic Python SDK):
  - model claude-opus-5-5, low effort (a short, simple writing task);
  - server-side refusal fallback enabled (betas server-side-fallback-2026-07-01,
    fallbacks="default"): if a safety classifier declines, the API retries
    on a fallback model inside the same call;
  - stop_reason is checked before the text is read.
"""

import json
import os
import re

MODEL = "claude-opus-5-5"

SYSTEM = (
    "You write short briefs for lunar mission managers. Use only the numbers in the "
    "facts you are given; never add, estimate or convert numbers. Plain English, no "
    "markdown, no lists."
)

PROMPT = (
    "Facts for one candidate landing site (JSON):\n{facts}\n\n"
    "Write exactly three sentences for a mission manager: the best landing time, how many "
    "usable days that gives out of the mission length, and the main risk (long darkness or "
    "little Earth contact). Copy every number exactly as it appears in the facts, and write whole "
    "numbers without \".0\"."
)

NUMBER = re.compile(r"(?<![A-Za-z_])-?\d+(?:\.\d+)?")


# ---------------- numbers guard ----------------

def _numbers_in(value):
    """Every number inside a facts value (dates and times included)."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        return [float(x) for x in NUMBER.findall(value)]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers_in(v)]
    if isinstance(value, (list, tuple)):
        return [n for v in value for n in _numbers_in(v)]
    return []


def allowed_numbers(facts):
    """Numbers the brief may use: each fact, and its normal roundings.

    A brief may say "62%" for 61.7 or "9.5" for 9.5, so for every fact we
    also allow it rounded to 0 and 1 decimals. Dates are split into parts
    (2027-02-12T06:00Z allows 2027, 2, 12, 6, 0), so "12 February" passes.
    """
    ok = set()
    for n in _numbers_in(facts):
        for v in (n, round(n), round(n, 1), abs(n), abs(round(n)), abs(round(n, 1))):
            ok.add(float(v))
    return ok


def check_numbers(text, facts):
    """Return the numbers in `text` that are NOT supported by `facts` (empty = pass)."""
    ok = allowed_numbers(facts)
    bad = []
    for raw in NUMBER.findall(text.replace(",", "")):
        v = float(raw)
        if v not in ok and abs(v) not in ok:
            bad.append(raw)
    return bad


# ---------------- template (no AI) ----------------

def template_brief(f):
    """Deterministic three-sentence brief built only from the facts.

    The third sentence names the real main risk, chosen from the numbers:
    a dark spell the rover can't survive, then thin Earth contact (under half
    the mission), then a survivable dark spell, else no risk in this window.
    """
    if not f["survives"]:
        risk = (f"The main risk is darkness: the longest dark spell is {f['longest_dark_h']:g} hours, "
                f"beyond the survivable limit of {f['max_dark_h']:g} hours.")
    elif f["contact_hours"] < f["mission_hours"] / 2:
        risk = (f"The main risk is Earth contact: only {f['contact_hours']:g} of {f['mission_hours']:g} "
                f"hours have Earth in view for direct communication.")
    elif f["longest_dark_h"] > 0:
        risk = (f"The main risk is darkness: the longest dark spell is {f['longest_dark_h']:g} hours, "
                f"within the survivable limit of {f['max_dark_h']:g} hours.")
    else:
        risk = (f"No dark spell occurs in this window, and Earth is in view for {f['contact_hours']:g} "
                f"of {f['mission_hours']:g} hours.")
    return (
        f"{f['name']} ranks {f['rank']} of {f['n_sites']} for {f['window']}, with the best landing at "
        f"{f['best_landing']}. "
        f"That landing gives {f['usable_days']:g} usable days out of a {f['mission_days']:g}-day mission, "
        f"with {f['sun_hours']:g} sunlit hours and {f['contact_hours']:g} hours of Earth contact. "
        + risk
    )


# ---------------- Claude ----------------

# Free-tier models tried in order (gemini-3.8-flash left out: busy or hanging on the free tier, Nov 2026).
GEMINI_MODELS = ([os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL")
                 else ["gemini-3.5-flash-lite", "gemini-3.5-flash"])
GEMINI_MODEL = GEMINI_MODELS[0]


def get_client():
    """The AI client to use: Gemini (free tier) if GEMINI_API_KEY is set, else Claude if
    ANTHROPIC_API_KEY is set, else None (template mode)."""
    if os.environ.get("GEMINI_API_KEY"):
        try:
            from google import genai
            return genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        except ImportError:
            pass
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        try:
            import anthropic
            return anthropic.Anthropic()
        except ImportError:
            pass
    return None


def client_name(client):
    if client is None:
        return "template (no GEMINI_API_KEY or ANTHROPIC_API_KEY set)"
    return (f"Gemini ({' / '.join(GEMINI_MODELS)}, free tier)" if hasattr(client, "interactions")
            else f"Claude ({MODEL})")


def gemini_brief(client, facts):
    """Ask Gemini for a brief. Returns the text, or None if it can't be used (e.g. free limit hit)."""
    for model in GEMINI_MODELS:
        try:
            inter = client.interactions.create(
                model=model, store=False, system_instruction=SYSTEM,
                input=PROMPT.format(facts=json.dumps(facts, indent=2)), timeout=30)
            return (inter.output_text or "").strip() or None
        except Exception as exc:  # busy, over the free limit, retired, network: try the next model
            print(f"    {model} unavailable ({type(exc).__name__}); trying the next model")
    return None


def ai_brief(client, facts):
    """Ask Claude for a brief. Returns the text, or None if it can't be used."""
    import anthropic

    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": PROMPT.format(facts=json.dumps(facts, indent=2))}],
        )
    except anthropic.RateLimitError as exc:
        print(f"    rate limited ({exc.status_code}); using template")
        return None
    except anthropic.APIStatusError as exc:
        print(f"    API error {exc.status_code}: {exc.message}; using template")
        return None
    except anthropic.APIConnectionError:
        print("    could not reach the API; using template")
        return None

    if response.stop_reason == "refusal":
        return None
    text = " ".join(b.text for b in response.content if b.type == "text").strip()
    return text or None


def generate_brief(facts, client=None, attempts=2):
    """Brief for one site plus where it came from ("ai" or "template")."""
    if client is not None:
        ask = gemini_brief if hasattr(client, "interactions") else ai_brief
        for _ in range(attempts):
            text = ask(client, facts)
            if text and not check_numbers(text, facts):
                return text, "ai"
    text = template_brief(facts)
    bad = check_numbers(text, facts)
    if bad:  # the template must always pass; if not, that's a bug to fix
        raise ValueError(f"template brief has unsupported numbers {bad}")
    return text, "template"
