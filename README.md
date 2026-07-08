# skincare-chatbot
AI skincare recommender with RAG retrieval, a multimodal image-analysis feature, and an evaluation harness — built end-to-end on Databricks (PySpark, MLflow) and deployed as a live app.
# Skincare AI Recommender

An AI-powered skincare recommendation chatbot, built end-to-end on Databricks — from raw, messy product data through a working RAG chatbot with an image-analysis feature, deployed as a live Databricks App.

I built this as a portfolio project to go deeper than a typical "wrap an LLM in a chat box" demo. The interesting part isn't the chatbot — it's the data engineering underneath it: real product datasets, real cleaning problems, ingredient validation against an official regulatory registry, and a recommendation system that's grounded in actual product data instead of an LLM guessing.

**Live app:** https://skincare-chatbot-7474652491521588.aws.databricksapps.com

## What it does

You can talk to it in plain English — "my skin is oily and I keep getting breakouts" — or upload a photo of your skin. Either way it:

1. Figures out what skin concern you're describing
2. Retrieves real products from the catalog that match, using a hybrid of semantic search (embeddings) and structured ingredient tags
3. Has an LLM write a recommendation, but only using the actual products and ingredients retrieved — no invented products, no invented benefits
4. For photos specifically, it looks at the image and does one of three things: recommend products, ask for a clearer photo, or — if something looks beyond a cosmetic concern — tell you to see a dermatologist instead of guessing at a diagnosis

## Why this data, and why it was harder than it sounds

The product catalog comes from three real sources: a Dermstore product export, a large Sephora products/reviews dataset, and the EU's official CosIng cosmetic ingredients registry (~31,000 ingredients). None of it arrived clean.

Ingredient lists were mixed comma- and newline-delimited. Prices were inconsistent strings. A chunk of the "skincare" catalog was actually haircare and devices that had leaked in. There was no reliable field saying "this product is good for acne" — that had to be derived from the ingredients themselves.

So the pipeline does real work before any AI shows up:

- Clean and normalize three separate sources (Databricks, PySpark) into a bronze → silver → gold structure
- Validate every product ingredient against the CosIng registry — this is also what filters out the non-skincare products, instead of a hand-written keyword blacklist. A product only counts as skincare if it actually contains enough recognized skincare ingredients.
- Build a small curated knowledge base mapping ~14 skin concerns to the ingredients that treat them, and use it to tag every product

None of this is glamorous, but it's the part that makes the recommendations trustworthy instead of hallucinated.

## The RAG layer, and what I actually learned building it

I went through three iterations on retrieval quality, and I think the failures are more interesting than the final result:

**v1 (plain semantic search):** worked, but was noticeably fuzzy — the top result for "oily skin and breakouts" was a product that didn't even treat acne, just because its embedding was vaguely close.

**Fix A (better embedding documents):** the first version buried each product's treated concerns under a wall of ingredients, so the embedding wasn't paying attention to the right thing. Rewriting the text to lead with the concerns fixed the ranking and tightened match scores.

**Fix B (hybrid retrieval):** semantic search alone still let irrelevant products slip in occasionally. The fix was to use embeddings to understand the query, but filter results through the exact concern tags before they're shown — meaning-matching for understanding, structured data for correctness.

I also built a small evaluation harness against the (sparse — only ~50 of 126 products) ground-truth concern labels in the raw data. It measured precision/recall around 0.10/0.28 on the 18 products with usable labels. I tried tightening the ingredient-matching rule to improve precision, and it made both metrics worse — the stricter rule assumed products would have multiple matching ingredients per concern, and in practice most don't. I reverted. I'd rather report an honest, modest number than a manipulated one, and the whole point of building the eval harness was catching exactly this kind of thing before it shipped.

MLflow tracks all three versions with their parameters and metrics, including the one marked `REVERTED`.

## Known limitations

- Concern-tagging precision/recall is low by the numbers above — the ground truth is sparse and my knowledge base only covers ~14 concerns with ~20 ingredients, so there's real room to improve this with a larger labeled set.
- A handful of haircare products still pass the ingredient-based skincare filter because they share common ingredients (glycerin, panthenol) with real skincare. A combined ingredient + category signal would fix this.
- Everything runs on free-tier infrastructure: an in-memory Chroma vector store instead of a managed vector DB, and Databricks' pay-per-token foundation models instead of a larger hosted model. Retrieval and generation both work, but a production version would swap these for Databricks Vector Search and a stronger LLM.
- The image-analysis escalation logic was verified with a controlled test and one real photo, not a proper clinical validation set — which is the honest way to test a feature like this without using medical images I don't have rights to.

## Architecture

Raw data (Dermstore, Sephora, CosIng)
        │
Cleaning & normalization (PySpark)  →  silver tables
        │
Ingredient validation + skincare filtering + concern tagging  →  gold tables
        │
Embeddings (sentence-transformers) + Chroma vector store
        │
Hybrid retrieval (semantic + concern tags)
        │
LLM generation (Databricks Llama 3.1), grounded in retrieved products only
        │
Gradio app (chat + photo upload) — deployed as a Databricks App

The image path runs a separate vision model (Llama 4 Maverick) that classifies a photo into recommend / escalate / retake before optionally handing off to the same recommendation pipeline.

## Repo structure

```
notebooks/
  1_cleaning_normalization.ipynb        cleaning all three raw sources
  2_transformation_structuring.ipynb    ingredient validation, filtering, concern tagging
  3_rag_chatbot_image.ipynb             embeddings, hybrid retrieval, chatbot, image path
  4_evaluation.ipynb                    ground-truth parsing, precision/recall, the v3 revert
app/
  app.py            the deployed Gradio app
  app.yaml          Databricks App config
  requirements.txt
```

The notebooks were built and run in Databricks (Free Edition), using Unity Catalog tables between stages. They're exported here as-is for reference — table paths inside them point at my workspace's catalog/schema and won't resolve without adjusting to your own.

## Stack

PySpark · Databricks (Unity Catalog, Delta tables, Free Edition foundation models, Databricks Apps) · sentence-transformers · ChromaDB · Gradio · MLflow

## What I'd do next

Swap in Databricks Vector Search for a production-grade vector store, expand the ground-truth evaluation set so precision/recall numbers are actually trustworthy, tighten the skincare filter to stop the haircare leak, and add location/weather-based feature signals to the recommendations.
