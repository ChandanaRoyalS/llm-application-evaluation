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
    assert trace["prompt_tokens"] == 200 and trace["total_latency_ms"] is not None  # triage + answer


def test_greeting_does_not_recommend(loaded_catalog, fake_llm):
    fake_llm.route = "off_topic"
    trace = core.run_pipeline("hello there")
    assert trace["status"] == "off_topic"
    assert trace["retrieved_product_ids"] == [] and trace["recommended_ids"] == []
    assert [c["triage"] for c in fake_llm.calls] == [True]   # no answer call wasted


def test_greeting_without_triage_still_does_not_recommend(loaded_catalog, fake_llm):
    trace = core.run_pipeline("hello there", use_triage=False)
    assert trace["status"] == "no_concern"
    assert fake_llm.calls == []


def test_medical_route_escalates_without_products(loaded_catalog, fake_llm):
    fake_llm.route = "medical"
    trace = core.run_pipeline("my mole is bleeding, which serum for dark spots?")
    assert trace["status"] == "escalated"
    assert trace["recommended_ids"] == [] and trace["retrieved_product_ids"] == []
    assert "dermatologist" in trace["answer"]
    assert trace["triage_route"] == "medical" and trace["prompt_tokens"] == 100


def test_out_of_scope_route(loaded_catalog, fake_llm):
    fake_llm.route = "out_of_scope"
    trace = core.run_pipeline("recommend a dry shampoo")
    assert trace["status"] == "out_of_scope" and trace["recommended_ids"] == []


def test_unparseable_triage_falls_back_to_normal_flow(loaded_catalog, fake_llm):
    fake_llm.triage_raw = "I think this is about skin."
    trace = core.run_pipeline("my skin is oily and I get acne breakouts")
    assert trace["triage_parse_ok"] is False and trace["triage_route"] == "cosmetic"
    assert trace["status"] == "ok"
    assert trace["prompt_tokens"] == 200     # triage + answer tokens are both counted


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


def test_llm_api_key_takes_precedence_over_hf_token(monkeypatch):
    import importlib
    from pipeline import config
    monkeypatch.setenv("HF_TOKEN", "hf_x")
    monkeypatch.setenv("LLM_API_KEY", "gsk_y")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    try:
        importlib.reload(config)
        assert config.LLM_API_KEY == "gsk_y" and config.USE_HF
        assert config.LLM_PROVIDER == "api.groq.com" != config.EVALUATED_PROVIDER
    finally:
        for k in ("HF_TOKEN", "LLM_API_KEY", "LLM_BASE_URL"):
            monkeypatch.delenv(k, raising=False)
        importlib.reload(config)


def test_extra_body_and_min_tokens_are_sent(monkeypatch):
    from pipeline import config, llm
    sent = {}

    class Resp:
        choices = [type("C", (), {"message": type("M", (), {"content": "OK"})()})()]
        usage = None

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    sent.update(kw)
                    return Resp()

    monkeypatch.setattr(llm, "_get_client", lambda: Client)
    monkeypatch.setattr(config, "LLM_EXTRA_BODY", {"reasoning_effort": "low"})
    monkeypatch.setattr(config, "LLM_MIN_MAX_TOKENS", 1024)
    assert llm.chat("m", [{"role": "user", "content": "hi"}], max_tokens=80)["text"] == "OK"
    assert sent["max_tokens"] == 1024 and sent["extra_body"] == {"reasoning_effort": "low"}


def test_temperature_can_be_omitted(monkeypatch):
    from pipeline import config, llm
    sent = {}

    class Resp:
        choices = [type("C", (), {"message": type("M", (), {"content": "OK"})()})()]
        usage = None

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    sent.clear(); sent.update(kw)
                    return Resp()

    monkeypatch.setattr(llm, "_get_client", lambda: Client)
    llm.chat("m", [{"role": "user", "content": "hi"}], temperature=0.0)
    assert sent["temperature"] == 0.0
    monkeypatch.setattr(config, "LLM_OMIT_TEMPERATURE", True)
    llm.chat("m", [{"role": "user", "content": "hi"}], temperature=0.0)
    assert "temperature" not in sent
