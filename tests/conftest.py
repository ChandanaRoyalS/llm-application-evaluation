"""Test setup: a tiny fake catalog, a fake embedding model and a fake LLM.

No network or model downloads are needed, so the tests run anywhere (and in CI).
The fake embedder is a bag-of-words over a fixed vocabulary, so similarity is
deterministic and easy to reason about.
"""
import json
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app"))

VOCAB = ["oily", "acne", "breakouts", "dry", "dryness", "flaky", "dark", "spots",
         "hyperpigmentation", "skin", "aging", "lines"]


class FakeEmbedder:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, texts):
        out = []
        for t in texts:
            words = t.lower().replace(",", " ").replace(".", " ").split()
            v = np.array([float(words.count(w)) for w in VOCAB]) + 1e-3
            out.append(v)
        return np.array(out)


PRODUCTS = [
    {"product_id": "1", "brand": "Acme", "name": "Clear Gel", "price": 20.0,
     "concerns": ["acne", "oily skin"], "ingredients": ["SALICYLIC ACID", "NIACINAMIDE"],
     "document": "helps with acne oily skin breakouts"},
    {"product_id": "2", "brand": "Hydra", "price": 0.0,
     "concerns": ["dryness"], "ingredients": ["GLYCERIN", "SQUALANE"],
     "document": "helps with dryness dry flaky skin"},
    {"product_id": "3", "brand": "Glow", "name": "Glow Brightening Serum", "price": 35.0,
     "concerns": ["hyperpigmentation"], "ingredients": ["ASCORBIC ACID"],
     "document": "helps with hyperpigmentation dark spots"},
]


@pytest.fixture
def loaded_catalog(tmp_path, monkeypatch):
    data_file = tmp_path / "app_data.json"
    data_file.write_text(json.dumps(PRODUCTS))

    fake_st = types.ModuleType("sentence_transformers")
    fake_st.SentenceTransformer = FakeEmbedder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)

    from pipeline import catalog
    monkeypatch.setattr(catalog, "DATA_PATH", str(data_file))
    catalog.STATE.update(ready=False, error=None)
    catalog.load()
    assert catalog.STATE["error"] is None, catalog.STATE["error"]
    return catalog


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the network call. Set fake_llm.reply (str) or fake_llm.fail = True."""
    from pipeline import llm

    class Fake:
        reply = '{"recommended_products": [1], "response": "Try the Clear Gel."}'
        route = "cosmetic"          # what the triage call returns
        triage_raw = None           # set to override the raw triage text
        fail = False
        calls = []

    def chat(model, messages, max_tokens=400, temperature=None):
        is_triage = messages[0]["content"].startswith("You route messages")
        Fake.calls.append({"model": model, "messages": messages, "triage": is_triage})
        if Fake.fail:
            raise llm.LLMError("simulated outage")
        text = (Fake.triage_raw or f'{{"route": "{Fake.route}", "reason": "test"}}') \
            if is_triage else Fake.reply
        return {"text": text, "model": model, "prompt_tokens": 100,
                "completion_tokens": 20, "latency_ms": 5, "cost_usd": None}

    Fake.calls = []
    monkeypatch.setattr(llm, "chat", chat)
    return Fake
