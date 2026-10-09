"""Show the evaluation inside the app (data: showcase.json, built by eval/build_showcase.py).

note(trace)        -> a short line under a chat answer: how this configuration did on the
                      locked test split for this kind of answer. It is a test-set result,
                      never a score of the live answer (a live question has no known answer).
case_choices(...)  -> recorded test cases for the explorer; render_case(id) -> markdown.
"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "showcase.json")
REPO = "https://github.com/ChandanaRoyalS/llm-application-evaluation"

try:
    with open(PATH, encoding="utf-8") as f:
        DATA = json.load(f)
except (OSError, ValueError):
    DATA = None


def _frac(s):
    return f"{s['k']} of {s['n']} ({100 * s['k'] / s['n']:.1f}%)"


def note(trace):
    """One-line test-set context for a chat answer, or '' if there is none."""
    if not DATA:
        return ""
    s, st = DATA["summary"], trace.get("status")
    if st == "escalated":
        msg = (f"On the locked test set, {_frac(s['escalation'])} messages that needed a doctor were sent to one.")
    elif st == "ok":
        msg = (f"On the locked test set, {_frac(s['quality'])} answers passed every quality check "
               f"(target {s['quality']['target']:.0%}, not yet met); {_frac(s['groundedness'])} named only "
               f"products and ingredients from the catalog.")
    elif st in ("off_topic", "out_of_scope"):
        msg = (f"On the locked test set, {_frac(s['off_topic'])} messages that shouldn't get products didn't get any.")
    elif st == "no_concern":
        c = s["cosmetic_no_concern"]
        msg = (f"Known weakness: on the locked test set, {c['k']} of {c['n']} real skincare questions got this "
               f"reply because the concern detector missed them. Try naming the concern (e.g. oily, dry, acne).")
    elif st == "no_products":
        msg = (f"On the locked test set, this reply was wrong for {_frac(s['false_no_products'])} questions "
               f"where suitable products existed.")
    else:
        return ""
    return (f"\n\n---\n<sub>📊 {msg} This is a test-set result, not a score of this answer. "
            f"See the **Evaluation explorer** tab.</sub>")


CATEGORIES = {
    "clear_single": "One clear concern", "multi_concern": "Several concerns", "slang_indirect": "Slang / indirect",
    "constraint": "Budget / product type", "not_in_catalog": "Not skincare", "off_topic": "Off-topic",
    "hidden_red_flag": "Hidden medical red flag", "clearly_medical": "Clearly medical",
    "injection": "Prompt injection", "trap": "Traps (negation, allergies)", "edge_case": "Edge cases",
}
ALL = "All categories"
RESULTS = ["All results", "Passed every check", "Failed a check"]


def case_choices(category=ALL, result=RESULTS[0]):
    if not DATA:
        return []
    out = []
    for c in DATA["cases"]:
        if category != ALL and CATEGORIES.get(c["category"], c["category"]) != category:
            continue
        if result == RESULTS[1] and not c["all_passed"] or result == RESULTS[2] and c["all_passed"]:
            continue
        mark = "✅" if c["all_passed"] else "❌"
        q = c["query"].strip().replace("\n", " ") or "(empty message)"
        out.append((f"{mark} {q[:80]}{'…' if len(q) > 80 else ''}", c["id"]))
    return out


def render_case(case_id):
    if not DATA or not case_id:
        return ""
    c = next((x for x in DATA["cases"] if x["id"] == case_id), None)
    if c is None:
        return ""
    exp = ("should be sent to a doctor" if c["expected"]["must_escalate"] else
           "should get product recommendations" if c["expected"]["should_recommend"] else
           "should get no products")
    q = c["query"].strip() or "(empty message)"
    lines = [f"**Category:** {CATEGORIES.get(c['category'], c['category'])} · **Expected:** this message {exp}",
             "", f"**Question:** {q}", "", f"**What the bot did:** {c['status_text']}", "",
             "**The bot's recorded answer:**", "", "> " + (c["answer"] or "—").replace("\n", "\n> ")]
    if c["products"]:
        lines += ["", "**Products recommended:** " + "; ".join(c["products"])]
    lines += ["", "**Automatic checks:**"]
    lines += [f"- {'✅' if x['ok'] else '❌'} {x['label']}" for x in c["checks"]]
    if c["quality"]:
        q = c["quality"]
        lines += ["", f"**Answer quality:** {'✅ passed every check' if q['passes'] else '❌ failed'}"]
        lines += [f"- ❌ {f['code']}: {f['text']}" for f in q["fails"]]
    return "\n".join(lines)


def header():
    if not DATA:
        return "Evaluation data isn't available in this deployment."
    s = DATA["summary"]
    gates = sum(1 for g in s["gates"] if g["passed"])
    return (f"These are the **{DATA['n_cases']} locked test cases** this exact configuration was evaluated on "
            f"({DATA['model'].split('/')[-1]}, pipeline {DATA['pipeline_version']}): the question, the bot's real "
            f"recorded answer, and how every check scored it. Nothing here is re-run, so it works even when the "
            f"chat model is unavailable.\n\n"
            f"**Safety and scope gates passed: {gates}/{len(s['gates'])}** · Doctor referrals when needed: "
            f"{_frac(s['escalation'])} · Answer quality: {_frac(s['quality'])} (target "
            f"{s['quality']['target']:.0%}, not met) · Prompt injections resisted: {_frac(s['injection'])}\n\n"
            f"Methods, statistics and limitations: [full write-up]({REPO}/blob/main/EVALUATION.md)")
