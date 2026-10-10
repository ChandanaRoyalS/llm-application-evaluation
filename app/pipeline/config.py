"""Runtime configuration, read from environment variables.

Backend is picked automatically:
  * HF_TOKEN set           -> Hugging Face Inference Providers (OpenAI-compatible)
  * LLM_API_KEY set        -> any OpenAI-compatible provider at LLM_BASE_URL (e.g. Groq);
                              takes precedence over HF_TOKEN for model calls, so HF_TOKEN
                              stays a Hugging Face token for model downloads
  * otherwise (Databricks) -> Databricks model serving via the SDK
"""
import json
import os

LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("HF_TOKEN")
USE_HF = bool(LLM_API_KEY)          # an OpenAI-compatible endpoint (Hugging Face by default)
HF_BASE_URL = os.environ.get("LLM_BASE_URL", "https://router.huggingface.co/v1")
# Where the live model calls go, for an honest label in the app: the evaluation ran on
# Hugging Face Inference Providers.
LLM_PROVIDER = HF_BASE_URL.split("//", 1)[-1].split("/", 1)[0]
EVALUATED_PROVIDER = "router.huggingface.co"
# For providers/models that need them (e.g. a reasoning model on Groq):
#   LLM_EXTRA_BODY='{"reasoning_effort": "low"}'  extra request fields, as JSON
#   LLM_MIN_MAX_TOKENS=1024                        raise every call's token limit to at least this,
#                                                  since a reasoning model's thinking counts against it
try:
    LLM_EXTRA_BODY = json.loads(os.environ.get("LLM_EXTRA_BODY", "") or "{}")
except json.JSONDecodeError:
    LLM_EXTRA_BODY = {}
LLM_MIN_MAX_TOKENS = int(os.environ.get("LLM_MIN_MAX_TOKENS", "0") or 0)

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

