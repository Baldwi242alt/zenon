"""Tests for landing scoring, ranking and the AI-brief numbers guard."""

from types import SimpleNamespace

from sunchaser_data import briefs
from sunchaser_data.metrics import PLACEHOLDER_CRITERIA
from sunchaser_data.scores import best_landing, rank_sites, scan_landings

FACTS = {
    "name": "Test Ridge", "rank": 2, "n_sites": 9, "window": "June 2027",
    "best_landing": "19 Jun 2027, 18:00 UTC", "mission_days": 10, "mission_hours": 240,
    "usable_days": 8.0, "sun_hours": 201.0, "contact_hours": 150.0, "both_hours": 120.0,
    "longest_dark_h": 9.0, "max_dark_h": 18, "survives": True,
}


# ---------- scoring ----------

def hourly_rows(n, sun=1.0, earth=True):
    return [{"time": f"2027-01-{1 + h // 24:02d}T{h % 24:02d}:00Z", "sun_frac": sun,
             "earth_visible": earth} for h in range(n)]


def test_scan_only_scores_landings_whose_mission_fits():
    rows = hourly_rows(24 * 12)                     # 12 days of data, 10-day mission
    scored = scan_landings(rows, PLACEHOLDER_CRITERIA, step_h=6)
    assert len(scored) == 9                         # landings at 0, 6, ..., 48 h
    assert all(s["usable_days"] == 10 for s in scored)


def test_surviving_landing_beats_more_usable_days():
    dead = {"landing": "a", "usable_days": 9, "longest_dark_h": 40, "contact_hours": 200, "survives": False}
    alive = {"landing": "b", "usable_days": 6, "longest_dark_h": 10, "contact_hours": 100, "survives": True}
    assert best_landing([dead, alive])["landing"] == "b"
    assert [sid for _, sid, _ in rank_sites({"x": dead, "y": alive})] == ["y", "x"]


# ---------- numbers guard ----------

def test_guard_accepts_facts_and_roundings():
    text = "Test Ridge ranks 2 of 9: land 19 Jun 2027 at 18:00 UTC for 8 usable days of 10, 201 sunlit hours."
    assert briefs.check_numbers(text, FACTS) == []


def test_guard_catches_invented_numbers():
    assert briefs.check_numbers("It gives 12 usable days and 97% survival.", FACTS) == ["12", "97"]


def test_template_always_passes_guard():
    for survives, contact, dark in [(True, 150.0, 9.0), (False, 150.0, 40.0), (True, 50.0, 0.0), (True, 200.0, 0.0)]:
        f = {**FACTS, "survives": survives, "contact_hours": contact, "longest_dark_h": dark}
        text = briefs.template_brief(f)
        assert briefs.check_numbers(text, f) == []
        assert text.count(". ") >= 2


# ---------- Claude path, with a fake client (no network) ----------

class FakeClient:
    """Mimics client.beta.messages.create and returns canned texts in order."""

    def __init__(self, texts, stop_reason="end_turn"):
        self.texts, self.calls = list(texts), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.stop_reason = stop_reason

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        text = self.texts.pop(0)
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=text)])


def test_good_ai_brief_is_used_and_request_is_well_formed():
    good = "Land at Test Ridge on 19 Jun 2027 at 18:00 UTC. It gives 8 of 10 usable days. Darkness peaks at 9 hours."
    client = FakeClient([good])
    text, source = briefs.generate_brief(FACTS, client)
    assert (text, source) == (good, "ai")
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]


def test_ai_brief_with_invented_number_falls_back_to_template():
    bad = "Land on 19 Jun 2027. You get 9.5 usable days and a 99% chance of success."
    client = FakeClient([bad, bad])
    text, source = briefs.generate_brief(FACTS, client)
    assert source == "template" and len(client.calls) == 2   # asked twice, then gave up


def test_refusal_falls_back_to_template():
    client = FakeClient(["", ""], stop_reason="refusal")
    _, source = briefs.generate_brief(FACTS, client)
    assert source == "template"
