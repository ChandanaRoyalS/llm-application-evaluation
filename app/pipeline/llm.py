"""Thin wrapper around the OpenAI-compatible chat API.

Every call returns a dict with the text plus the measurements the
evaluation needs: token counts, latency and (if a price is configured) cost.
Failures raise LLMError so callers can show a friendly message.
"""
import logging
import os
import time

from openai import OpenAI

from . import config

log = logging.getLogger(__name__)

_hf_client = None
_workspace = None


class LLMError(RuntimeError):
    """Raised when the model call fails (network, rate limit, bad response...)."""


def _get_client():
    global _hf_client, _workspace
    if config.USE_HF:
        if _hf_client is None:
            _hf_client = OpenAI(api_key=config.LLM_API_KEY,
                                base_url=config.HF_BASE_URL, timeout=60)
        return _hf_client
    # Databricks: build from the SDK's auth config (refreshes tokens automatically)
    from databricks.sdk import WorkspaceClient
    if _workspace is None:
        _workspace = WorkspaceClient()
    headers = _workspace.config.authenticate()
    token = headers["Authorization"].split(" ", 1)[1]
    return OpenAI(api_key=token, base_url=f"{_workspace.config.host}/serving-endpoints",
                  timeout=60)


def _cost(model, prompt_tokens, completion_tokens):
    price = config.MODEL_PRICES.get(model)
    if not price or prompt_tokens is None or completion_tokens is None:
        return None
    return (prompt_tokens * price.get("input", 0)
            + completion_tokens * price.get("output", 0)) / 1_000_000


def chat(model, messages, max_tokens=400, temperature=None):
    """Call the model. Returns {text, model, prompt_tokens, completion_tokens,
    latency_ms, cost_usd}. Raises LLMError on any failure."""
    kwargs = {"model": model, "messages": messages,
              "max_tokens": max(max_tokens, config.LLM_MIN_MAX_TOKENS)}
    if temperature is not None and not config.LLM_OMIT_TEMPERATURE:
        kwargs["temperature"] = temperature
    if config.LLM_EXTRA_BODY:
        kwargs["extra_body"] = config.LLM_EXTRA_BODY
    start = time.perf_counter()
    try:
        response = _get_client().chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
    except Exception as e:  # network errors, 4xx/5xx, malformed responses
        log.warning("LLM call failed (model=%s): %s", model, e)
        raise LLMError(str(e)) from e
    latency_ms = round((time.perf_counter() - start) * 1000)

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    return {
        "text": text,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "cost_usd": _cost(model, prompt_tokens, completion_tokens),
    }
