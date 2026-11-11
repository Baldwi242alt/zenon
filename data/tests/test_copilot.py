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
