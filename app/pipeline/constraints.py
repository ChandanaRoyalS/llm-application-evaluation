"""Use the product type and budget the user asks for in retrieval (pipeline v3).

Like product_filter.py, the product-side rules use only the product name (world
knowledge about what a "wash" or "pads" are), not the evaluation's independent
catalog labels, so the evaluation can still grade them.

parse(query)        -> {"forms": set of requested forms, "max_price": float or None}
product_forms(p)    -> set of forms a product is, from its name
satisfies(p, c)     -> True if the product meets every parsed constraint
"""
import re

# requested form -> patterns in the user's message
QUERY_FORMS = {
    "eye cream": r"\beye\s*(cream|gel|serum|balm|treatment)s?\b",
    # a request for a cleanser, not a mention of washing ("I wash my face twice a day")
    "cleanser": r"\bcleansers?\b|\b(face|facial)\s*wash(es)?\b|\bcleansing\s+(balm|oil|gel|foam|milk|water)\b",
    "toner": r"\btoners?\b",
    "serum": r"\bserums?\b",
    "moisturizer": r"\bmoisturi[sz]ers?\b|\bface\s*creams?\b|\bnight\s*creams?\b|\bday\s*creams?\b",
    "mask": r"\bmasks?\b",
    "exfoliant": r"\bexfolia(tor|tors|nt|nts|ting)\b|\bscrubs?\b|\bpads\b"
                 r"|\b(a|an|chemical|facial|face|at-home|gentle|mild|peeling)\s+(peel|pads?)\b",  # "my skin peels" is not a request
    "sunscreen": r"\bsunscreens?\b|\bsun\s*cream\b|\bspf\b|\bsunblock\b",
    "oil": r"\b(face|facial|an?|beauty)\s+oils?\b",
}

# product form -> words in the product name
PRODUCT_FORMS = {
    "eye cream": ("eye",),
    "cleanser": ("cleanser", "cleansing", "wash"),
    "toner": ("toner", "lotion", "essence"),
    "serum": ("serum", "concentre", "concentrate", "complex", "solution", "drops"),
    "moisturizer": ("moisturi", "cream", "crème", "creme", "milk", "balm", "veil"),
    "mask": ("mask",),
    "exfoliant": ("exfolia", "scrub", "peel", "pads", "polish"),
    "sunscreen": ("spf", "sunscreen", "solar", "uv "),
    "oil": (" oil",),
}
NOT_A_FORM = ("oil-free", "oil free")

PRICE_RE = re.compile(
    r"(?:under|below|less\s+than|cheaper\s+than|max(?:imum)?|up\s+to|no\s+more\s+than|"
    r"budget(?:\s+(?:of|is|around|about|~))?|around|about|within|<)\s*\$?\s*(\d+(?:\.\d+)?)"
    r"|\$\s*(\d+(?:\.\d+)?)\s*(?:or\s+(?:less|under)|max)", re.I)


def parse(query):
    q = (query or "").lower()
    forms = {f for f, pat in QUERY_FORMS.items() if re.search(pat, q)}
    if "eye cream" in forms:  # "eye cream" also matches the moisturizer pattern words
        forms.discard("moisturizer")
    m = PRICE_RE.search(q)
    price = None
    if m and ("$" in q or re.search(r"budget|under|below|less than|cheaper", q)):
        price = float(m.group(1) or m.group(2))
    return {"forms": forms, "max_price": price}


def product_forms(p):
    name = f" {(p.get('name') or '').lower()} "
    for w in NOT_A_FORM:
        name = name.replace(w, " ")
    forms = {f for f, words in PRODUCT_FORMS.items() if any(w in name for w in words)}
    if "eye cream" in forms:      # an eye product is an eye cream, not a face moisturizer
        forms.discard("moisturizer")
    return forms


def satisfies(p, c):
    if c["forms"] and not (product_forms(p) & c["forms"]):
        return False
    if c["max_price"] is not None:
        try:
            price = float(p.get("price"))
        except (TypeError, ValueError):
            return False          # unknown price can't be shown to meet a budget
        if price > c["max_price"]:
            return False
    return True


def active(c):
    return bool(c["forms"]) or c["max_price"] is not None


def describe(c):
    """Short text for the no-match message, e.g. 'a serum under $40'."""
    parts = []
    if c["forms"]:
        parts.append(" or ".join(("an " if f[0] in "aeiou" else "a ") + f for f in sorted(c["forms"])))
    else:
        parts.append("a product")
    if c["max_price"] is not None:
        parts.append(f"under ${c['max_price']:g}")
    return " ".join(parts)
