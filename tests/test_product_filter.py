"""Pipeline v2: product filter and the concern hint (EVAL_SPEC changelog v1.12)."""
from pipeline import config, generation, product_filter as pf


def test_non_skincare_products_are_dropped():
    assert not pf.is_skincare({"brand": "R+Co", "name": "R+Co TELEVISION Perfect Hair Shampoo"})
    assert not pf.is_skincare({"brand": "Glo Skin Beauty", "name": "Glo Skin Beauty Under Eye Concealer"})
    assert not pf.is_skincare({"brand": "miriam quevedo", "name": "Dermstore Exclusive Black Baccara Set"})
    assert pf.is_skincare({"brand": "Paula's Choice", "name": "Paula's Choice CLEAR Pore Normalizing Cleanser"})


def test_areas_follow_the_user():
    assert pf.allowed_areas("My hands are really dry.") == {"hand"}
    assert pf.allowed_areas("dry lips") == {"lip"}
    assert pf.allowed_areas("acne on my chest and back") == {"face", "eye", "body"}
    assert pf.allowed_areas("oily skin") == {"face", "eye"}
    hand_cream = {"name": "Oribe Nourishing Hand Crème"}
    assert not pf.keep(hand_cream, pf.allowed_areas("oily skin"))
    assert pf.keep(hand_cream, pf.allowed_areas("my hands are dry"))


def test_detected_concerns_not_given_to_the_model_by_default(monkeypatch):
    msgs = generation.build_messages("my skin is dull", ["oily skin"], "1. X")
    assert "oily skin" not in msgs[1]["content"]
    assert "never tell the user they have" in msgs[0]["content"]
    monkeypatch.setattr(config, "CONCERN_HINT", True)
    assert "The user's concern(s): oily skin" in generation.build_messages("x", ["oily skin"], "1. X")[1]["content"]
