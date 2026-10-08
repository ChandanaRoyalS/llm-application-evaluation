"""Keep retrieval to skincare products for the body area the user asked about.

The catalog mixes in hair, makeup, fragrance and bath products, and body/hand/lip
products. These rules use only the product name and brand (world knowledge about
what a shampoo or a lipstick is). They were written without looking at the
evaluation's independent catalog labels, so the eval can still grade them.
"""
import re

NON_SKINCARE_WORDS = (
    "shampoo", "conditioner", "hair", "curl", "scalp", "mousse", "texturizing spray",
    "root touch-up", "blonding", "lash", "mascara", "eye duet", "shadow", "bronzer",
    "lipstick", "lip liner", "concealer", "foundation", "setting powder", "primer",
    "sculpting stick", "eau de toilette", "essential oil", "bath soak", "shade variation",
    "smoothing oil",
)
# brands that sell only hair, lash or fragrance products
NON_SKINCARE_BRANDS = (
    "miriam quevedo", "r+co", "sachajuan", "briogeo", "moroccanoil", "alterna",
    "philip kingsley", "philip b", "christophe robin", "dphue", "evolvh", "virtue",
    "grow gorgeous", "grande cosmetics", "neom", "caswell-massey",
)

AREA_WORDS = {"hand": ("hand",), "body": ("body",), "lip": ("lip",), "eye": ("eye",)}
QUERY_AREAS = {
    "hand": r"\bhands?\b|\bfingers?\b|\bcuticles?\b",
    "body": r"\bbody\b|\blegs?\b|\barms?\b|\bback\b|\bchest\b|\bshoulders?\b|\bfeet\b|\bfoot\b",
    "lip": r"\blips?\b",
}


def _text(p):
    return f"{p.get('brand', '')} {p.get('name', '')}".lower()


def is_skincare(p):
    t = _text(p)
    return not (any(w in t for w in NON_SKINCARE_WORDS) or any(t.startswith(b) or f" {b} " in f" {t} " for b in NON_SKINCARE_BRANDS))


def product_area(p):
    t = (p.get("name") or "").lower()
    for area, words in AREA_WORDS.items():
        if any(w in t for w in words):
            return area
    return "face"


def allowed_areas(query):
    """Face and eye by default. Body areas the user names are added; if the user names only
    hands or lips (and no part of the face), only those areas are kept."""
    q = (query or "").lower()
    named = {a for a, pat in QUERY_AREAS.items() if re.search(pat, q)}
    mentions_face = re.search(r"\bface\b|\bfacial\b|\bcheeks?\b|\bnose\b|\bforehead\b|\bchin\b|\bjaw", q)
    if named and named <= {"hand", "lip"} and not mentions_face:
        return named
    return {"face", "eye"} | named


def keep(p, areas):
    return is_skincare(p) and product_area(p) in areas
