---
title: Skincare Recommendation Assistant
emoji: 🧴
colorFrom: pink
colorTo: purple
sdk: gradio
sdk_version: 5.34.2
app_file: app.py
pinned: false
short_description: RAG skincare recommender with photo analysis
---

# Skincare Recommendation Assistant — app

This folder is the deployable app. It runs on **Hugging Face Spaces**
and still runs on **Databricks Apps** unchanged.

| Where | LLM backend | What it needs |
|---|---|---|
| Hugging Face Space | Hugging Face Inference Providers | `HF_TOKEN` secret |
| Databricks App | Databricks model serving | nothing — uses the app's service principal |

The default text model is **Llama 3.3 70B**, the configuration selected by the evaluation (see `EVALUATION.md` in the repo root).
Optional overrides (Space → Settings → Variables): `TEXT_MODEL`, `VISION_MODEL`, `LLM_BASE_URL`, `TRIAGE_ENABLED`, `PRODUCT_FILTER`.

**Using another OpenAI-compatible provider (e.g. Groq's free tier):** add a secret `LLM_API_KEY` with that provider's key and set the variables `LLM_BASE_URL` (e.g. `https://api.groq.com/openai/v1`) and `TEXT_MODEL` (e.g. `llama-3.3-70b-versatile`). `LLM_API_KEY` is used for model calls instead of `HF_TOKEN`. The app then shows a note that the live chat is served by a different provider than the one the evaluation used.

## Deploy to Hugging Face Spaces

1. Create a Gradio Space (CPU basic hardware).
2. Upload the contents of this `app/` folder: `app.py`, the `pipeline/` folder,
   `app_data.json` (the product catalog), `requirements.txt` and this `README.md`.
3. Create a token at huggingface.co/settings/tokens with "Make calls to Inference Providers" enabled.
4. In the Space: Settings → Variables and secrets → New secret → `HF_TOKEN`.

Optional: `MODEL_PRICES` (JSON, USD per 1M tokens) turns on cost tracking (the numbers below are placeholders — use your provider's actual prices):
`{"meta-llama/Llama-3.1-8B-Instruct": {"input": 0.05, "output": 0.08}}`.
