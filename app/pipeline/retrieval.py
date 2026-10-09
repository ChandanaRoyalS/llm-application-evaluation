"""Concern detection + hybrid retrieval (semantic ranking, concern-tag filter)."""
import numpy as np

from . import catalog, config, constraints, product_filter


def score_concerns(query_text):
    """Cosine similarity between the query and every known concern, best first."""
    model = catalog.get_model()
    q = model.encode([query_text])[0]
    c = catalog.get_concern_embeddings()
    sims = (c @ q) / (np.linalg.norm(c, axis=1) * np.linalg.norm(q))
    scores = [(concern, float(s)) for concern, s in zip(catalog.ALL_CONCERNS, sims)]
    return sorted(scores, key=lambda x: -x[1])


def select_concerns(scores, top_k=config.CONCERN_TOP_K, threshold=config.CONCERN_THRESHOLD):
    """Keep up to top_k concerns at or above the threshold.

    Returns [] when nothing clears the threshold — a greeting or off-topic
    message should not be forced into a skin concern.
    """
    return [c for c, s in scores[:top_k] if s >= threshold]


def detect_concerns(query_text):
    scores = score_concerns(query_text)
    return select_concerns(scores), scores


def retrieve(query_text, concerns, n=config.N_PRODUCTS, pool=config.CANDIDATE_POOL):
    """Rank products semantically, keep skincare for the asked-about area (PRODUCT_FILTER)
    of the requested type and budget (CONSTRAINT_FILTER), tagged with a detected concern."""
    model = catalog.get_model()
    collection = catalog.get_collection()
    q = model.encode([query_text])[0].tolist()
    con = constraints.parse(query_text) if config.CONSTRAINT_FILTER else None
    if con and constraints.active(con):
        pool = collection.count()     # a narrow request may match only a few products: rank them all
    res = collection.query(query_embeddings=[q], n_results=min(pool, collection.count()))
    areas = product_filter.allowed_areas(query_text)
    matched, fits = [], []
    for pid, meta in zip(res["ids"][0], res["metadatas"][0]):
        product = catalog.PRODUCTS.get(pid, {})
        if config.PRODUCT_FILTER and not product_filter.keep(product, areas):
            continue
        if con and not constraints.satisfies(product, con):
            continue
        fits.append(pid)
        tags = [t.strip() for t in meta["concerns"].split(",") if t.strip()]
        if any(c in tags for c in concerns):
            matched.append(pid)
        if len(matched) >= n:
            break
    if not matched and con and constraints.active(con):
        # The type/budget leaves few products, and the catalog's concern tags (and the
        # concern detector) are unreliable, so an empty tag match is often a false
        # "nothing fits". Fall back to the closest products that meet the request.
        return fits[:config.CONSTRAINT_FALLBACK]
    return matched
