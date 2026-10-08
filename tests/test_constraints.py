"""Pipeline v3: requested product type and budget used in retrieval (EVAL_SPEC changelog v1.19)."""
import pipeline
from pipeline import config, constraints as C, retrieval


def test_requested_forms_and_budget_are_parsed():
    assert C.parse("A cleanser for acne.") == {"forms": {"cleanser"}, "max_price": None}
    assert C.parse("An exfoliant for rough texture.")["forms"] == {"exfoliant"}
    assert C.parse("an eye cream for puffiness")["forms"] == {"eye cream"}
    assert C.parse("Something under $30 for dark spots.") == {"forms": set(), "max_price": 30.0}
    assert C.parse("Something for redness, budget around $50.")["max_price"] == 50.0
    assert C.parse("under 30 dollars for acne")["max_price"] == 30.0


def test_mentions_are_not_requests():
    for q in ("my skin is oily", "I want oil-free stuff for oily skin", "I wash my face twice a day",
              "my skin peels in winter", "I'm on a budget", "I'm 30 and have acne", "money is no object"):
        assert not C.active(C.parse(q)), q


def test_product_forms_from_the_name():
    assert C.product_forms({"name": "Paula's Choice CLEAR Pore Normalizing Cleanser"}) == {"cleanser"}
    assert C.product_forms({"name": "COOLA Clear Skin Oil-Free Moisturiser SPF 30"}) == {"moisturizer", "sunscreen"}
    assert C.product_forms({"name": "Bioderma Sensibio Eye Contour"}) == {"eye cream"}
    assert C.product_forms({"name": "Replenix Gly-Sal 10-2 Clarifying Pads"}) == {"exfoliant"}
    assert C.product_forms({"name": "VivierSkin LEXXEL"}) == set()      # unknown form: never matches a request


def test_satisfies_type_and_budget():
    serum = {"name": "Glow Brightening Serum", "price": 35.0}
    assert C.satisfies(serum, C.parse("a serum for dark spots"))
    assert not C.satisfies(serum, C.parse("a mask for dark spots"))
    assert not C.satisfies(serum, C.parse("dark spots under $30"))
    assert not C.satisfies({"name": "X Serum"}, C.parse("under $30"))   # unknown price can't meet a budget
    assert C.describe(C.parse("an exfoliant under $40")) == "an exfoliant under $40"


def test_retrieval_keeps_only_matching_products(loaded_catalog, monkeypatch):
    monkeypatch.setattr(config, "CONSTRAINT_FILTER", True)
    assert retrieval.retrieve("a serum for dark spots", ["hyperpigmentation"]) == ["3"]
    assert retrieval.retrieve("oily acne gel under $25", ["acne"]) == ["1"]
    assert retrieval.retrieve("oily acne under $10", ["acne"]) == []
    monkeypatch.setattr(config, "CONSTRAINT_FILTER", False)               # pipeline v2 ignores them
    assert retrieval.retrieve("oily acne under $10", ["acne"]) == ["1"]


def test_no_match_says_what_was_not_found(loaded_catalog, fake_llm, monkeypatch):
    monkeypatch.setattr(config, "CONSTRAINT_FILTER", True)
    t = pipeline.run_pipeline("a mask for acne and oily skin breakouts")
    assert t["status"] == "no_products" and t["constraints"] == {"forms": ["mask"], "max_price": None}
    assert "couldn't find a mask" in t["answer"]


def test_pipeline_version():
    assert config.pipeline_version() == "v3"
