"""Parsing of model outputs — the part most likely to break silently."""
from pipeline import generation, vision

NUM_TO_ID = {1: "a", 2: "b", 3: "c"}


def test_parse_clean_json():
    out = generation.parse_response(
        '{"recommended_products": [1, 3], "response": "Hello"}', NUM_TO_ID)
    assert out == {"answer": "Hello", "recommended_ids": ["a", "c"],
                   "invalid_numbers": [], "parse_ok": True, "removed_links": []}


def test_parse_fenced_json_with_chatter():
    raw = 'Sure!\n```json\n{"recommended_products": ["2"], "response": "Hi"}\n```'
    out = generation.parse_response(raw, NUM_TO_ID)
    assert out["parse_ok"] and out["recommended_ids"] == ["b"]


def test_parse_flags_numbers_never_offered():
    out = generation.parse_response(
        '{"recommended_products": [1, 7], "response": "x"}', NUM_TO_ID)
    assert out["recommended_ids"] == ["a"]
    assert out["invalid_numbers"] == [7]


def test_parse_deduplicates():
    out = generation.parse_response(
        '{"recommended_products": [1, 1], "response": "x"}', NUM_TO_ID)
    assert out["recommended_ids"] == ["a"]


def test_parse_failure_falls_back_to_raw_text():
    out = generation.parse_response("Just plain text, no JSON.", NUM_TO_ID)
    assert out["parse_ok"] is False
    assert out["recommended_ids"] is None
    assert out["answer"] == "Just plain text, no JSON."


def test_vision_valid_decision():
    out = vision.parse_decision(
        '{"decision": "Escalate", "concerns": [], "observation": "x"}')
    assert out["decision"] == "escalate" and out["parse_ok"]


def test_vision_invalid_decision_falls_back_to_retake():
    out = vision.parse_decision('{"decision": "diagnose", "concerns": ["acne"]}')
    assert out["decision"] == "retake" and out["parse_ok"] is False


def test_vision_garbage_falls_back_to_retake():
    out = vision.parse_decision("I cannot help with that.")
    assert out["decision"] == "retake" and out["parse_ok"] is False


def test_triage_route_parsing():
    from pipeline import triage
    assert triage.parse_route('{"route": "Medical", "reason": "bleeding mole"}')[:2] == ("medical", "bleeding mole")
    assert triage.parse_route('```json\n{"route": "out-of-scope"}\n```')[0] == "out_of_scope"
    assert triage.parse_route("no idea") == ("cosmetic", "triage output could not be parsed", False)
    assert triage.parse_route('{"route": "dangerous"}')[2] is False
