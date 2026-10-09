"""The evaluation shown in the app must match the committed evaluation files exactly."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "eval"))

import build_showcase  # noqa: E402
import showcase  # noqa: E402  (app/showcase.py)


def test_showcase_json_is_up_to_date_with_the_test_run():
    run = os.path.join(ROOT, "eval", "results", build_showcase.DEFAULT_RUN)
    rebuilt = build_showcase.build(run, os.path.join(ROOT, "eval", "datasets", "test.jsonl"),
                                   os.path.join(run, "quality.json"), os.path.join(ROOT, "app", "app_data.json"))
    committed = json.load(open(os.path.join(ROOT, "app", "showcase.json"), encoding="utf-8"))
    assert committed == json.loads(json.dumps(rebuilt)), "re-run: python eval/build_showcase.py"


def test_numbers_match_the_metrics():
    met = json.load(open(os.path.join(ROOT, "eval", "results", build_showcase.DEFAULT_RUN, "metrics.json")))
    s = showcase.DATA["summary"]
    assert (s["escalation"]["k"], s["escalation"]["n"]) == (met["metrics"]["escalation_recall"]["k"],
                                                             met["metrics"]["escalation_recall"]["n"])
    assert showcase.DATA["n_cases"] == len(met["per_case"]) == 156
    assert sum(g["passed"] for g in s["gates"]) == 7


def test_note_is_a_test_set_result_not_a_score():
    for status in ("ok", "escalated", "off_topic", "out_of_scope", "no_concern", "no_products"):
        n = showcase.note({"status": status})
        assert "locked test set" in n and "not a score of this answer" in n
    assert showcase.note({"status": "llm_error"}) == ""
    assert "36 of 37" in showcase.note({"status": "escalated"})


def test_explorer_filters_and_renders():
    assert len(showcase.case_choices()) == 156
    failed = showcase.case_choices("Hidden medical red flag", "Failed a check")
    assert failed and all(label.startswith("❌") for label, _ in failed)
    md = showcase.render_case("hidden_red_flag-016")
    assert "Not sent to a doctor, although it needed one" in md and "A5" in md
