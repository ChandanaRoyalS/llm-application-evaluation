"""Product catalog + vector store, loaded once at startup.

Loading is slow (embedding model download + encoding), so the app calls
load() in a background thread and checks is_ready() before answering.
"""
import json
import logging
import os

from . import config

log = logging.getLogger(__name__)

DATA_PATH = os.environ.get(
    "APP_DATA_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_data.json"))

STATE = {"ready": False, "error": None}
PRODUCTS = {}           # product_id -> product dict
ALL_CONCERNS = []
_model = None
_collection = None
_concern_embeddings = None


def is_ready():
    return STATE["ready"]


def get_model():
    return _model


def get_collection():
    return _collection


def get_concern_embeddings():
    return _concern_embeddings


def price_or_none(product):
    """Missing prices were exported as 0.0 — treat anything <= 0 as unknown."""
    price = product.get("price")
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def display_name(product):
    """Brand + product name. Older catalog exports have no name field."""
    name = (product.get("name") or "").strip()
    brand = (product.get("brand") or "").strip()
    if name and brand and not name.lower().startswith(brand.lower()):
        return f"{brand} {name}"
    return name or f"{brand} (product name not available)"


def load():
    global _model, _collection, _concern_embeddings
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb

        with open(DATA_PATH) as f:
            records = json.load(f)
        PRODUCTS.clear()
        PRODUCTS.update({str(p["product_id"]): p for p in records})
        log.info("Loaded %d products from %s", len(PRODUCTS), DATA_PATH)

        _model = SentenceTransformer(config.EMBEDDING_MODEL)
        docs = [p["document"] for p in records]
        embeddings = _model.encode(docs)

        client = chromadb.Client()
        try:
            client.delete_collection("skincare_products")
        except Exception:
            pass
        _collection = client.create_collection("skincare_products")
        _collection.add(
            ids=[str(p["product_id"]) for p in records],
            embeddings=[e.tolist() for e in embeddings],
            documents=docs,
            metadatas=[{"concerns": ", ".join(p.get("concerns", []))} for p in records],
        )

        ALL_CONCERNS[:] = sorted({c for p in records for c in p.get("concerns", [])})
        _concern_embeddings = _model.encode(ALL_CONCERNS)

        STATE["ready"] = True
        log.info("Catalog ready: %d products, %d concerns", len(PRODUCTS), len(ALL_CONCERNS))
    except Exception as e:
        STATE["error"] = str(e)
        log.exception("Startup failed")
