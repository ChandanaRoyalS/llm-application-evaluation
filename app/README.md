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

Optional overrides (Space → Settings → Variables): `TEXT_MODEL`, `VISION_MODEL`, `LLM_BASE_URL`.

## Deploy to Hugging Face Spaces

1. Create a Gradio Space (CPU basic hardware).
2. Upload `app.py`, `requirements.txt`, this `README.md`, and `app_data.json`
   (the product catalog; git-ignored here, so upload it separately).
3. Create a token at huggingface.co/settings/tokens with "Make calls to Inference Providers" enabled.
4. In the Space: Settings → Variables and secrets → New secret → `HF_TOKEN`.
