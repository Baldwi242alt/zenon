"""Tests for the copilot: tools on real data, request checks, and the tool loop with a fake Claude."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("copilot", Path(__file__).resolve().parents[2] / "api" / "copilot.py")
copilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copilot)


# ---------- tools on the real shared/ data ----------

def test_every_tool_schema_is_strict():
    for t in copilot.tool_schemas():
        s = t["input_schema"]
        assert t["strict"] is True and s["additionalProperties"] is False
        assert sorted(s["required"]) == sorted(s["properties"])


def test_compare_sites_matches_scores_file_for_scored_month():
    scores = json.loads((copilot.SHARED / "scores.json").read_text())
    month = scores["window_start"][:7]
    data, facts = copilot.tool_compare_sites(month, [])
    top = data["ranked"][0]
    assert top["site"] == scores["sites"][0]["site"]
    assert top["usable_days"] == scores["sites"][0]["usable_days"]
    assert len(facts) == 2 * len(copilot.site_ids())


def test_slip_cost_divides_budget_by_usable_days():
    data, _ = copilot.tool_slip_cost("malapert_massif", "2027-06-13T18:00Z", 1_000_000)
    zero = data["slips"][0]
    assert zero["slip_days"] == 0 and zero["landing"] == "2027-06-13T18:00Z"
    if zero["usable_days"]:
        assert zero["cost_per_usable_day"] == round(1_000_000 / zero["usable_days"])
    assert [s["slip_days"] for s in data["slips"]] == [0, 1, 2, 3, 7]


def test_bad_tool_input_becomes_an_error_result():
    text, facts, is_error = copilot.run_tool("get_site_summary", {"site": "atlantis"})
    assert is_error and facts == [] and "unknown site" in text


# ---------- request validation ----------

def test_request_checks():
    assert copilot.handle(b"not json")[0] == 400
    assert copilot.handle(json.dumps({"question": ""}).encode())[0] == 400
    assert copilot.handle(json.dumps({"question": "x" * 501}).encode())[0] == 400
    assert copilot.handle(json.dumps({"question": "hi", "site": "atlantis"}).encode())[0] == 400


def test_no_api_key_falls_back_to_fact_finder(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    status, body = copilot.handle(json.dumps({"question": "Which site is best in June?"}).encode(), ip="nokey")
    assert status == 200 and "June 2027" in body["answer"] and body["facts_used"]


# ---------- the loop, with a fake Claude ----------

def block(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


class FakeClaude:
    """Replays scripted responses for client.beta.messages.create."""

    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def scripted(final_texts):
    """First Claude asks compare_sites for June, then answers with each text in turn."""
    first = SimpleNamespace(stop_reason="tool_use", content=[
        block("text", text="Let me compare."),
        block("tool_use", id="t1", name="compare_sites", input={"month": "2027-06", "site_list": []})])
    finals = [SimpleNamespace(stop_reason="end_turn", content=[block("text", text=t)]) for t in final_texts]
    return FakeClaude([first] + finals)


def test_grounded_answer_passes_with_facts():
    data, _ = copilot.tool_compare_sites("2027-06", [])
    top = data["ranked"][0]
    answer = f"{top['name']} is best in June with {top['usable_days']:g} usable days."
    fake = scripted([answer])
    out = copilot.answer_question("Best site in June?", client=fake)
    assert out["answer"] == answer
    assert any(top["name"] in f["label"] for f in out["facts_used"])
    req = fake.calls[0]
    assert req["model"] == "claude-opus-5-5" and req["fallbacks"] == "default"
    # The tool result went back to Claude as the user turn after the tool call.
    # (The fake keeps a reference to the growing message list, so index from the start.)
    tool_turn = fake.calls[1]["messages"][2]
    assert tool_turn["role"] == "user" and tool_turn["content"][0]["tool_use_id"] == "t1"


def test_invented_number_is_caught_and_never_returned():
    fake = scripted(["Site X gives 99.5 usable days.", "Still 99.5 usable days."])
    out = copilot.answer_question("Best site in June?", client=fake)
    assert "99.5" not in out["answer"]
    assert out["facts_used"]          # falls back to the verified facts
    # Claude was told which number was unsupported.
    nudges = [m["content"] for m in fake.calls[-1]["messages"] if isinstance(m["content"], str)]
    assert any("99.5" in n for n in nudges)


# ---------- fact finder (no AI) ----------

def test_fact_finder_answers_common_questions_from_tool_numbers():
    best, _ = copilot.tool_compare_sites("2027-06", [])
    out = copilot.answer_without_ai("Which site is best in June?")
    assert best["ranked"][0]["name"] in out["answer"]

    stats, _ = copilot.tool_timeline_stats("haworth", "2027-08-01", "2027-08-31")
    out = copilot.answer_without_ai("How dark does Haworth get in August?")
    assert f"{stats['longest_dark_h']} hours" in out["answer"]


def test_fact_finder_reads_budgets_and_ignores_day_counts():
    assert copilot._find_budget("2-day slip with a $50 million budget") == 50e6
    assert copilot._find_budget("budget 2000000, what if it slips") == 2e6
    assert copilot._find_budget("what does a 2-day slip cost") is None


def test_site_names_are_matched_as_words():
    # "Slater" contains "late"; it must not trigger the slip answer.
    out = copilot.answer_without_ai("Compare Slater and Nobile Rim 1 in October")
    assert "slip" not in out["answer"] and "Slater Plain" in out["answer"]


def test_unknown_question_gets_suggestions():
    out = copilot.answer_without_ai("What is the meaning of life?")
    assert out["facts_used"] == [] and "Try:" in out["answer"]


# ---------- Gemini path, with a fake client (no network) ----------

class Step(SimpleNamespace):
    def model_dump(self):
        return dict(self.__dict__)


class FakeGemini:
    """Mimics client.interactions.create; returns scripted interactions in order."""

    def __init__(self, interactions=None, error=None):
        self.queue, self.calls, self.error = list(interactions or []), [], error
        self.interactions = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.queue.pop(0)


def gemini_script(final_texts):
    call = SimpleNamespace(steps=[Step(type="function_call", id="c1", name="compare_sites",
                                       arguments={"month": "2027-06", "site_list": []})], output_text="")
    finals = [SimpleNamespace(steps=[Step(type="model_output", text=t)], output_text=t) for t in final_texts]
    return FakeGemini([call] + finals)


def test_gemini_grounded_answer():
    data, _ = copilot.tool_compare_sites("2027-06", [])
    top = data["ranked"][0]
    answer = f"{top['name']} is best in June with {top['usable_days']:g} usable days."
    fake = gemini_script([answer])
    status, body = copilot.handle(json.dumps({"question": "Best site in June?"}).encode(),
                                  ip="g1", engine="gemini", client=fake)
    assert status == 200 and body["answer"] == answer
    assert fake.calls[0]["model"] == copilot.GEMINI_MODEL and fake.calls[0]["store"] is False
    # The tool result went back to Gemini with the matching call id.
    sent = fake.calls[1]["input"]
    assert any(m.get("type") == "function_result" and m.get("call_id") == "c1" for m in sent)


def test_gemini_invented_number_falls_back_to_fact_finder():
    fake = gemini_script(["Cabeus gives 99.5 usable days.", "Still 99.5 usable days."])
    status, body = copilot.handle(json.dumps({"question": "Which site is best in June?"}).encode(),
                                  ip="g2", engine="gemini", client=fake)
    assert status == 200 and "99.5" not in body["answer"] and "June 2027" in body["answer"]


def test_gemini_quota_used_up_falls_back_to_fact_finder():
    from google.genai import errors
    quota = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    status, body = copilot.handle(json.dumps({"question": "Which site is best in June?"}).encode(),
                                  ip="g3", engine="gemini", client=FakeGemini(error=quota))
    assert status == 200 and "June 2027" in body["answer"]


def test_busy_gemini_model_moves_to_the_next_one():
    data, _ = copilot.tool_compare_sites("2027-06", [])
    top = data["ranked"][0]
    answer = f"{top['name']} is best in June with {top['usable_days']:g} usable days."
    script = gemini_script([answer])
    calls = []

    def create(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "busy-model":
            raise RuntimeError("503 high demand")
        return script.queue.pop(0)

    fake = SimpleNamespace(interactions=SimpleNamespace(create=create))
    out = copilot.answer_with_gemini("Best site in June?", None, fake, models=["busy-model", "ok-model"])
    assert out["answer"] == answer
    # First call tried both; after that the conversation stays on the model that answered.
    assert calls == ["busy-model", "ok-model", "ok-model"]


def gemini_says(*texts):
    """A fake Gemini that answers directly, without calling any tool."""
    return FakeGemini([SimpleNamespace(steps=[Step(type="model_output", text=t)], output_text=t) for t in texts])


def test_general_question_is_answered_conversationally():
    answer = "The Moon is about 384,400 km away, and at the south pole Earth hangs low on the horizon."
    fake = gemini_says(answer)
    status, body = copilot.handle(json.dumps({"question": "How far away is the Moon?"}).encode(),
                                  ip="g5", engine="gemini", client=fake)
    assert status == 200 and body["answer"] == answer and body["kind"] == "general" and body["facts_used"] == []


def test_general_answer_may_not_invent_site_numbers():
    name = copilot.site_name(copilot.site_ids()[0])
    fake = gemini_says(f"{name} gets 99 usable days.", f"{name} gets 98 usable days.")
    status, body = copilot.handle(json.dumps({"question": f"How good is {name}?"}).encode(),
                                  ip="g6", engine="gemini", client=fake)
    assert status == 200 and "99" not in body["answer"] and "98" not in body["answer"]


def test_history_is_sent_for_follow_ups():
    fake = gemini_says("Sure: in August the Sun is lower at that site.")
    history = [{"role": "user", "text": "Tell me about Haworth"}, {"role": "assistant", "text": "Haworth is a crater rim."}]
    copilot.handle(json.dumps({"question": "What about August?", "history": history}).encode(),
                   ip="g7", engine="gemini", client=fake)
    first = fake.calls[0]["input"][0]["content"][0]["text"]
    assert "Tell me about Haworth" in first and "What about August?" in first


# ---------- stage 15: live analysis and rover routes ----------

def test_custom_mission_with_default_rules_matches_precomputed_windows():
    # With the standard rules (10 days, 12 sun h, 4 contact h, 18 h dark limit) the live analysis
    # must reproduce the precomputed windows file exactly.
    data, facts = copilot.tool_analyze_custom_mission("mons_mouton", "2027-06", 10, 12, 4, 18)
    rows = {r["landing"]: r for r in copilot.load("windows_mons_mouton.json")["rows"]}
    pre = rows[data["best"]["landing"]]
    assert data["best"]["usable_days"] == pre["usable_days"]
    assert data["best"]["longest_dark_h"] == pre["longest_dark_h"]
    assert data["landings_survivable"] == sum(r["survives"] for l, r in rows.items() if l.startswith("2027-06"))


def test_custom_mission_changes_with_the_rules():
    strict, _ = copilot.tool_analyze_custom_mission("haworth", "2027-08", 10, 12, 4, 6)
    loose, _ = copilot.tool_analyze_custom_mission("haworth", "2027-08", 10, 12, 4, 200)
    assert loose["landings_survivable"] >= strict["landings_survivable"]
    assert loose["landings_survivable"] == loose["landings_tested"]      # a 200 h limit is never exceeded here
    text, _, is_error = copilot.run_tool("analyze_custom_mission",
                                         {"site": "haworth", "month": "2027-08", "mission_days": 500,
                                          "min_sun_hours": 12, "min_contact_hours": 4, "max_dark_hours": 18})
    assert is_error and "between 1 and 60" in text


def test_rover_routes_tool_reports_the_planner_file():
    if not (copilot.SHARED / "route_slater_plain.json").exists():
        pytest.skip("routes not built")
    data, facts = copilot.tool_get_rover_routes("slater_plain")
    raw = json.loads((copilot.SHARED / "route_slater_plain.json").read_text())
    assert [r["name"] for r in data["routes"]] == [r["name"] for r in raw["routes"]]
    assert data["routes"][0]["survival_probability"] == raw["routes"][0]["survival_probability"]
    out = copilot.answer_without_ai("Does the rover survive at Slater Plain?")
    assert "Shortest path" in out["answer"] and "Sunchaser" in out["answer"]


def test_fact_finder_runs_a_custom_mission_analysis():
    out = copilot.answer_without_ai("Best landing for a 5-day mission at Mons Mouton in June?")
    assert "5-day mission" in out["answer"] and "Mons Mouton" in out["answer"]
