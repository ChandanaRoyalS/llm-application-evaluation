"""Runtime configuration, read from environment variables.

Backend is picked automatically:
  * HF_TOKEN set           -> Hugging Face Inference Providers (OpenAI-compatible)
  * otherwise (Databricks) -> Databricks model serving via the SDK
"""
import json
import os

USE_HF = bool(os.environ.get("HF_TOKEN"))
HF_BASE_URL = os.environ.get("LLM_BASE_URL", "https://router.huggingface.co/v1")

if USE_HF:
    DEFAULT_TEXT_MODEL = os.environ.get("TEXT_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
    DEFAULT_VISION_MODEL = os.environ.get(
        "VISION_MODEL", "meta-llama/Llama-4-Maverick-17B-128E-Instruct")
else:
    DEFAULT_TEXT_MODEL = os.environ.get("TEXT_MODEL", "databricks-meta-llama-3-3-70b-instruct")
    DEFAULT_VISION_MODEL = os.environ.get("VISION_MODEL", "databricks-llama-4-maverick")

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Triage runs before concern detection and routes medical, out-of-scope and
# off-topic messages away from product recommendations. By default it uses the
# same model as the answer, so comparing models changes only one variable.
TRIAGE_ENABLED = os.environ.get("TRIAGE_ENABLED", "1") not in ("0", "false", "False")
TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL") or None

# Retrieval settings
CONCERN_TOP_K = 3
CONCERN_THRESHOLD = 0.45      # below this, a query is treated as "no skin concern detected"
CANDIDATE_POOL = 30           # semantic candidates fetched before the concern-tag filter
N_PRODUCTS = 5                # products passed to the LLM

# Optional price table for cost tracking, USD per 1M tokens, e.g.
# (placeholder numbers) MODEL_PRICES='{"meta-llama/Llama-3.1-8B-Instruct": {"input": 0.05, "output": 0.08}}'
# Models missing from the table get cost_usd = None (unknown), never a guess.
try:
    MODEL_PRICES = json.loads(os.environ.get("MODEL_PRICES", "{}"))
except json.JSONDecodeError:
    MODEL_PRICES = {}

# Pipeline v2 (see EVAL_SPEC changelog v1.12). Both default on; set to 0 to reproduce v1.
PRODUCT_FILTER = os.environ.get("PRODUCT_FILTER", "1") not in ("0", "false", "False")
CONCERN_HINT = os.environ.get("CONCERN_HINT", "0") not in ("0", "false", "False")

# Pipeline v3 (EVAL_SPEC changelog v1.19): retrieval keeps only products of the type
# and within the budget the user asks for (app/pipeline/constraints.py). 0 = v2.
CONSTRAINT_FILTER = os.environ.get("CONSTRAINT_FILTER", "1") not in ("0", "false", "False")


def pipeline_version():
    if not PRODUCT_FILTER or CONCERN_HINT:
        return "v1"
    return "v3" if CONSTRAINT_FILTER else "v2"

