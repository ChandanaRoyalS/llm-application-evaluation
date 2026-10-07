"""Concern detection + hybrid retrieval (semantic ranking, concern-tag filter)."""
import numpy as np

from . import catalog, config


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
    """Rank products semantically, keep those tagged with a detected concern."""
    model = catalog.get_model()
    collection = catalog.get_collection()
    q = model.encode([query_text])[0].tolist()
    res = collection.query(query_embeddings=[q], n_results=min(pool, collection.count()))
    matched = []
    for pid, meta in zip(res["ids"][0], res["metadatas"][0]):
        tags = [t.strip() for t in meta["concerns"].split(",") if t.strip()]
        if any(c in tags for c in concerns):
            matched.append(pid)
        if len(matched) >= n:
            break
    return matched
