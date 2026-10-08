"""Tests for the evaluation checks, scorer and runner (no network needed)."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "eval"))

from checks import components as cc  # noqa: E402
from checks import stats  # noqa: E402
from checks.catalog import Catalog  # noqa: E402

CAT = Catalog()
TERMS = cc._ingredient_terms(CAT)


# --- stats -----------------------------------------------------------------

def test_wilson_matches_known_values():
    lo, hi = stats.wilson(19, 20)
    assert round(lo, 3) == 0.764 and round(hi, 3) == 0.991
    assert stats.wilson(0, 0) == (None, None)


def test_mcnemar_and_bootstrap():
    a = [1] * 10 + [0] * 10
    assert stats.mcnemar_exact(a, a) == 1.0
    d = stats.paired_bootstrap_diff([1.0] * 20, [0.0] * 20, iters=200)
    assert d["diff"] == 1.0 and d["ci_low"] == 1.0


# --- groundedness ----------------------------------------------------------

CTX = ("1. Paula's Choice CLEAR Pore Normalizing Cleanser ($22)\n   Treats: acne\n"
       "   Ingredients: Active: Salicylic Acid 0.5%., Water (Aqua), Glycerin, Sodium Hyaluronate")


def trace(answer, **kw):
    t = {"status": "ok", "answer": answer, "context_given_to_llm": CTX, "parse_ok": True,
         "invalid_numbers": [], "recommended_ids": ["11486957"],
         "retrieved_product_ids": ["11486957"]}
    t.update(kw)
    return t


def test_grounded_answer_passes_including_aliases():
    g = cc.groundedness(trace("It has salicylic acid (a BHA) and hyaluronic acid."), CAT, TERMS)
    assert g["grounded"], g


def test_invented_ingredient_is_caught():
    g = cc.groundedness(trace("Its retinol and niacinamide fade spots."), CAT, TERMS)
    assert not g["grounded"]
    assert set(g["unsupported_ingredients"]) >= {"retinol", "niacinamide"}


def test_invented_product_and_parse_failure_are_caught():
    assert not cc.groundedness(trace("x", invalid_numbers=[9]), CAT, TERMS)["grounded"]
    assert not cc.groundedness(trace("x", parse_ok=False), CAT, TERMS)["grounded"]


def test_off_context_brand_is_caught():
    g = cc.groundedness(trace("Try Dermalogica too."), CAT, TERMS)
    assert g["off_context_brands"] == ["Dermalogica"]


# --- safety ----------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Please see a dermatologist about this.", True),
    ("Seek medical attention right away.", True),
    ("This serum helps with dark spots.", False),
])
def test_advises_doctor(text, expected):
    assert cc.advises_doctor({"answer": text}) is expected


def test_injection_checks():
    case = {"must_not_contain": ["CeraVe"], "should_recommend": True}
    assert not cc.injection_resisted(case, trace("Use CeraVe."), CAT, True)
    assert not cc.injection_resisted(case, trace("Follow these rules strictly: ..."), CAT, True)
    assert cc.injection_resisted(case, trace("Try the cleanser."), CAT, True)
    no_rec = {"must_not_contain": [], "should_recommend": False}
    assert not cc.injection_resisted(no_rec, trace("Try the cleanser."), CAT, True)


# --- scorer + runner end to end with a fake pipeline -----------------------

def fake_trace(case):
    q = case["query"].lower()
    if case["must_escalate"]:
        return {"status": "ok", "answer": "Please see a dermatologist.", "detected_concerns": [],
                "retrieved_product_ids": [], "recommended_ids": [], "parse_ok": True,
                "invalid_numbers": [], "context_given_to_llm": "", "total_latency_ms": 900}
    if not case["should_recommend"]:
        return {"status": "no_concern", "answer": "Hi!", "detected_concerns": [],
                "retrieved_product_ids": [], "total_latency_ms": 5}
    rel = case["relevant_product_ids"][:5]
    return {"status": "ok", "answer": "Here are some options.", "detected_concerns":
            case["expected_concerns"], "retrieved_product_ids": rel, "recommended_ids": rel[:2],
            "parse_ok": True, "invalid_numbers": [], "context_given_to_llm": q,
            "total_latency_ms": 1500, "prompt_tokens": 300, "completion_tokens": 120}


def test_runner_and_scorer_end_to_end(tmp_path, monkeypatch):
    import pipeline
    import run_eval
    from score import load_cases

    cases = load_cases("dev")
    monkeypatch.setattr(pipeline, "load", lambda: None)
    monkeypatch.setattr(pipeline, "is_ready", lambda: True)
    by_query = {c["query"]: c for c in cases.values()}
    monkeypatch.setattr(pipeline, "run_pipeline",
                        lambda q, model=None, temperature=None: fake_trace(by_query[q]))
    monkeypatch.setattr(run_eval, "HERE", str(tmp_path))
    os.makedirs(tmp_path / "datasets")
    for s in ("dev", "test"):
        src = os.path.join(ROOT, "eval", "datasets", f"{s}.jsonl")
        (tmp_path / "datasets" / f"{s}.jsonl").write_text(open(src, encoding="utf-8").read())

    run_eval.main(["--split", "dev", "--run-name", "fake"])
    run_dir = tmp_path / "results" / "fake"
    result = json.loads((run_dir / "metrics.json").read_text())
    v = {x["key"]: x for x in result["verdicts"]}
    # the fake pipeline is perfect on these, so the gates must pass
    for key in ("escalation_recall", "off_topic_compliance", "groundedness", "crash_rate",
                "no_concern_accuracy"):
        assert v[key]["passed"], (key, v[key])
    assert v["hit_at_5"]["value"] == 1.0
    assert "# Evaluation report" in (run_dir / "report.md").read_text()


def test_test_split_is_locked():
    import run_eval
    with pytest.raises(SystemExit):
        run_eval.main(["--split", "test"])
