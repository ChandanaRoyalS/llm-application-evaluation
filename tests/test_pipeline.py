"""End-to-end behaviour of run_pipeline with a fake embedder and fake LLM."""
from pipeline import catalog, core, retrieval


def test_select_concerns_returns_empty_below_threshold():
    scores = [("acne", 0.30), ("dryness", 0.20)]
    assert retrieval.select_concerns(scores, threshold=0.45) == []


def test_select_concerns_keeps_top_k_above_threshold():
    scores = [("acne", 0.9), ("oily skin", 0.6), ("dryness", 0.5), ("aging", 0.46)]
    assert retrieval.select_concerns(scores, top_k=3, threshold=0.45) == \
        ["acne", "oily skin", "dryness"]


def test_price_and_name_helpers():
    assert catalog.price_or_none({"price": 0.0}) is None
    assert catalog.price_or_none({"price": None}) is None
    assert catalog.price_or_none({"price": 12.5}) == 12.5
    assert catalog.display_name({"brand": "Acme", "name": "Clear Gel"}) == "Acme Clear Gel"
    assert catalog.display_name({"brand": "Glow", "name": "Glow Serum"}) == "Glow Serum"
    assert "not available" in catalog.display_name({"brand": "Hydra"})


def test_happy_path_trace(loaded_catalog, fake_llm):
    trace = core.run_pipeline("my skin is oily and I get acne breakouts")
    assert trace["status"] == "ok"
    assert "acne" in trace["detected_concerns"]
    assert trace["retrieved_product_ids"][0] == "1"
    assert "Acme Clear Gel" in trace["context_given_to_llm"]
    assert trace["recommended_ids"] == ["1"]
    assert trace["parse_ok"] is True
    assert trace["answer"] == "Try the Clear Gel."
    assert trace["prompt_tokens"] == 100 and trace["total_latency_ms"] is not None


def test_greeting_does_not_recommend(loaded_catalog, fake_llm):
    trace = core.run_pipeline("hello there")
    assert trace["status"] == "no_concern"
    assert trace["retrieved_product_ids"] == []
    assert fake_llm.calls == []          # no model call wasted


def test_empty_input(loaded_catalog, fake_llm):
    assert core.run_pipeline("   ")["status"] == "empty_input"


def test_llm_outage_gives_friendly_message(loaded_catalog, fake_llm):
    fake_llm.fail = True
    trace = core.run_pipeline("dry flaky skin dryness")
    assert trace["status"] == "llm_error"
    assert trace["answer"] == core.MSG_LLM_ERROR
    assert "simulated outage" in trace["error"]


def test_missing_price_is_not_shown_as_zero(loaded_catalog, fake_llm):
    trace = core.run_pipeline("dry flaky skin dryness")
    assert "$0" not in trace["context_given_to_llm"]
    assert "price not listed" in trace["context_given_to_llm"]


def test_model_is_passed_through(loaded_catalog, fake_llm):
    trace = core.run_pipeline("dark spots hyperpigmentation", model="some/other-model")
    assert trace["model"] == "some/other-model"
    assert fake_llm.calls[0]["model"] == "some/other-model"


def test_not_ready(monkeypatch):
    monkeypatch.setitem(catalog.STATE, "ready", False)
    monkeypatch.setitem(catalog.STATE, "error", None)
    assert core.run_pipeline("oily skin")["status"] == "not_ready"
