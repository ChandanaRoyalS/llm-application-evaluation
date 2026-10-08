"""Grounded generation with structured output.

The model must answer with JSON naming the products it recommends by their
list number. That makes groundedness checkable with code: every recommended
number must exist in the context we gave it.
"""
import json
import re

from . import catalog, config

SYSTEM_PROMPT = (
    "You are a knowledgeable, friendly skincare assistant. Follow these rules strictly:\n"
    "1. Recommend ONLY products from the provided list. Never invent products.\n"
    "2. When explaining why a product helps, refer ONLY to the ingredients and "
    "concerns actually listed for that product. Do NOT invent ingredients, "
    "benefits, claims, or product links.\n"
    "3. Address ONLY the concerns in the user's own message. A product's 'Treats' list is "
    "not the user's concern: never tell the user they have oily skin, acne or any other "
    "concern they did not mention.\n"
    "4. Keep a warm but professional tone. No pet names.\n"
    "5. Give cosmetic guidance only. Do NOT diagnose medical conditions. If the "
    "concern sounds severe or medical, gently suggest seeing a dermatologist.\n"
    "6. Reply ONLY with a JSON object, no other text:\n"
    '{"recommended_products": [list of product numbers you recommend], '
    '"response": "your message to the user"}'
)


def build_context(product_ids):
    """Numbered product list for the prompt. Returns (text, {number: product_id})."""
    lines, number_to_id = [], {}
    for i, pid in enumerate(product_ids, 1):
        p = catalog.PRODUCTS[pid]
        price = catalog.price_or_none(p)
        price_txt = f"${price:.0f}" if price is not None else "price not listed"
        ings = ", ".join(p.get("ingredients", [])[:8])
        lines.append(f"{i}. {catalog.display_name(p)} ({price_txt})\n"
                     f"   Treats: {', '.join(p.get('concerns', []))}\n"
                     f"   Ingredients: {ings}")
        number_to_id[i] = pid
    return "\n".join(lines), number_to_id


def build_messages(query_text, concerns, context_text):
    user_prompt = (
        f'User\'s message: "{query_text}"\n\n'
        + (f"The user's concern(s): {', '.join(concerns)}\n\n" if config.CONCERN_HINT else "") +
        f"Products from our catalog (use ONLY these, and only their listed ingredients):\n"
        f"{context_text}\n\n"
        f"Write a warm, professional recommendation. Mention specific ingredients "
        f"from the list to explain why each product helps with the user's concern.")
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}]


def _extract_json_object(text):
    """Find and parse the first {...} block, tolerating ```json fences and chatter."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def parse_response(raw_text, number_to_id):
    """Parse the model's JSON answer.

    Returns dict(answer, recommended_ids, invalid_numbers, parse_ok).
    If parsing fails, the raw text is shown to the user and recommended_ids
    is None (unknown) so the evaluation can count it as a parse failure.
    """
    obj = _extract_json_object(raw_text)
    if not isinstance(obj, dict) or not isinstance(obj.get("response"), str):
        return {"answer": raw_text.strip(), "recommended_ids": None,
                "invalid_numbers": [], "parse_ok": False}

    recommended, invalid = [], []
    for n in obj.get("recommended_products") or []:
        try:
            n = int(n)
        except (TypeError, ValueError):
            invalid.append(n)
            continue
        if n in number_to_id:
            if number_to_id[n] not in recommended:
                recommended.append(number_to_id[n])
        else:
            invalid.append(n)   # a number we never offered = hallucinated product
    return {"answer": obj["response"].strip(), "recommended_ids": recommended,
            "invalid_numbers": invalid, "parse_ok": True}
