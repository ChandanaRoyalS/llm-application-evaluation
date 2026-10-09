# LLM Application Evaluation

An end-to-end evaluation of an LLM application: a skincare product recommender (retrieval over a real product catalog, LLM triage and grounded generation), deployed on Hugging Face Spaces.

The evaluation is the point of the project: 260 hand-written test cases, a locked test split, safety gates and a model-selection rule fixed before any results, paired statistics, an LLM judge validated against reference labels before it was trusted, and a CI gate that runs the evaluation on every pull request. The app underneath was built end-to-end on Databricks, from raw, messy product data to a working chatbot.

**Live app:** [huggingface.co/spaces/chandanaroyal719/skincare-chatbot](https://huggingface.co/spaces/chandanaroyal719/skincare-chatbot) — runs the evaluated configuration: Llama 3.3 70B with triage and pipeline v2

## Evaluation at a glance

The core of the project is an application-level evaluation: 260 hand-written cases across 11 failure types (hidden medical red flags, prompt injection, budgets, slang…), a locked test split, gates and a model-selection rule fixed in advance in [EVAL_SPEC.md](EVAL_SPEC.md), paired statistics, and an LLM judge that was validated against reference labels before being trusted. Full write-up: **[EVALUATION.md](EVALUATION.md)**.

| Locked test split (156 cases) | Start | End |
|---|---|---|
| Safety and scope gates | 5/7 | **7/7**, stable across 4 runs |
| Told to see a doctor when they should be | 5.4% | **97.3%** |
| Wrong-category products retrieved | 17.0% | **1.5%** |
| Answer quality (target ≥ 85%) | 43.5% | **77.9%** (paired +32.8 pp, p = 3·10⁻⁶) — target not met |

What the evaluation found: the original bot sent most medical red flags a greeting (fixed with a triage step); a bigger model didn't fix answer quality because the cause was in the pipeline (the concern detector's guesses were passed to the model as facts, and 45 of 106 catalog products weren't skincare); and the LLM judge passed validation for *Appropriate* (κ = 0.78) but not for *Helpful* (κ = 0.44), so *Helpful* is scored by code and hand labels instead.

Every pull request also runs a fixed 24-case smoke set through the real pipeline ([eval-gate workflow](.github/workflows/eval-gate.yml)); the check fails if any safety or scope gate fails.

## What it does

You can talk to it in plain English — "my skin is oily and I keep getting breakouts" — or upload a photo of your skin. Either way it:

1. Figures out what skin concern you're describing
2. Retrieves real products from the catalog that match, using a hybrid of semantic search (embeddings) and structured ingredient tags
3. Has an LLM write a recommendation, but only using the actual products and ingredients retrieved — no invented products, no invented benefits
4. For photos specifically, it looks at the image and does one of three things: recommend products, ask for a clearer photo, or — if something looks beyond a cosmetic concern — tell you to see a dermatologist instead of guessing at a diagnosis

## Why this data, and why it was harder than it sounds

The project works with three real datasets: a Dermstore product export (120 products), a large Sephora products dataset (~8,500 products), and the EU's official CosIng cosmetic ingredients registry (~31,000 ingredients). The recommender's catalog is built from Dermstore and validated against CosIng; the Sephora data is cleaned in notebook 1 but not yet merged into the catalog. None of it arrived clean.

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

I also built a small evaluation harness against the (sparse — only 50 of 120 products) ground-truth concern labels in the raw data. It measured precision/recall around 0.10/0.28 on the 18 products with usable labels (bootstrap 95% intervals 0.03–0.18 and 0.11–0.47, too wide to tell small changes apart). I tried tightening the ingredient-matching rule to improve precision, and it made both metrics worse — the stricter rule assumed products would have multiple matching ingredients per concern, and in practice most don't. I reverted. I'd rather report an honest, modest number than a manipulated one, and the whole point of building the eval harness was catching exactly this kind of thing before it shipped.

The full v2 → v3 → revert history is in notebook 4. One caveat I found later: the revert cell rebuilds the tags with a top-15 ingredient cutoff (267 tags), which isn't identical to notebook 2's original tagging (420 tags). Reconciling the two is part of the evaluation work described below.

## Known limitations

- Concern-tagging precision/recall is low by the numbers above — the ground truth is sparse and my knowledge base only covers ~14 concerns with ~20 ingredients, so there's real room to improve this with a larger labeled set.
- The catalog's skincare filter leaks: labeled product by product, only 61 of the 106 catalog products are skincare; the rest are haircare (25), makeup (15), fragrance (3), a bath soak and a device gel. They pass the ingredient-based filter because they share common ingredients (glycerin, panthenol) with real skincare. Retrieval now drops them with name- and brand-based rules (pipeline v2, wrong-category picks 17% → 1.5%); fixing the catalog itself is still to do.
- Evaluation limits (synthetic single-author dataset, AI-written reference labels, small red-flag and injection samples) are listed in [EVALUATION.md](EVALUATION.md#limitations).
- The catalog export is being updated to include product names; older exports only carry the brand, so answers may refer to a product by brand alone.
- The chat is single-turn: each message is answered on its own, without conversation history.
- Everything runs on lightweight infrastructure: an in-memory Chroma vector store instead of a managed vector DB, and small open Llama models served through Hugging Face Inference Providers instead of a larger hosted model. Retrieval and generation both work, but a production version would swap these for a managed vector store (e.g. Databricks Vector Search) and a stronger LLM.
- The image-analysis escalation logic was verified with a controlled test and one real photo, not a proper clinical validation set — which is the honest way to test a feature like this without using medical images I don't have rights to.

## Architecture

```
Raw data (Dermstore, Sephora, CosIng)
        │
Cleaning & normalization (PySpark)  →  silver tables
        │
Ingredient validation + skincare filtering + concern tagging  →  gold tables
        │
Embeddings (sentence-transformers) + Chroma vector store
        │
Triage: medical / out of scope / off topic / cosmetic  (medical → refer to a doctor)
        │
Hybrid retrieval (semantic + concern tags) + skincare / body-area filter
        │
LLM generation (Llama 3.3 70B), grounded in retrieved products only, JSON output
        │
Gradio app (chat + photo upload) — deployed on Hugging Face Spaces
```

The image path runs a separate vision model (Llama 4 Maverick) that classifies a photo into recommend / escalate / retake before optionally handing off to the same recommendation pipeline.

## Repo structure

```
Notebooks/
  1_cleaning_normalization.ipynb        cleaning all three raw sources
  2_transformation_structuring.ipynb    ingredient validation, filtering, concern tagging
  3_rag_chatbot_image.ipynb             embeddings, hybrid retrieval, chatbot, image path, catalog export
  4_evaluation.ipynb                    ground-truth parsing, precision/recall, the v3 revert
app/
  app.py            Gradio UI (runs on Hugging Face Spaces or Databricks Apps)
  pipeline/         all app logic — shared by the UI and the evaluation
    core.py         run_pipeline() / run_image_pipeline(): return a trace of every step
    triage.py       routes medical, out-of-scope and off-topic messages before anything else
    retrieval.py    concern detection + hybrid retrieval
    generation.py   grounded prompt + structured (JSON) output parsing
    vision.py       photo triage: recommend / escalate / retake
    catalog.py      product catalog + vector store
    llm.py          model calls with token, latency and cost tracking
  app_data.json     the product catalog (exported by notebook 3)
  README.md         Hugging Face Space config + deploy steps
  app.yaml          Databricks App config (original deployment)
  requirements.txt  pinned runtime dependencies
eval/               the evaluation: datasets, runner, scoring, comparisons, LLM judge, all results
tests/              unit tests (no network or model downloads needed)
EVAL_SPEC.md        what "good" means, fixed before results, with a changelog of every change
EVALUATION.md       the evaluation write-up
```

`run_pipeline(query, model)` returns the answer plus a record of every step — detected concerns, retrieved products, the exact context the LLM saw, its raw output, the products it recommended, tokens, latency and cost. The model is a parameter, so different models can be compared on identical inputs.

The notebooks were built and run in Databricks (Free Edition), using Unity Catalog tables between stages. The app was first deployed as a Databricks App and later moved to Hugging Face Spaces so it's always reachable. The notebooks are exported here as-is for reference — table paths inside them point at my workspace's catalog/schema and won't resolve without adjusting to your own.

## Running locally

```bash
cd app
pip install -r requirements.txt
export HF_TOKEN=hf_...        # token with "Make calls to Inference Providers" enabled
python app.py                 # http://localhost:7860
```

Tests (lightweight — no torch or model downloads):

```bash
pip install -r requirements-dev.txt
pytest
```

## Stack

PySpark · Databricks (Unity Catalog, Delta tables) · sentence-transformers · ChromaDB · Gradio · Hugging Face Spaces + Inference Providers (Llama 3.3 70B, Llama 4 Maverick; DeepSeek-V3.2 as the evaluation judge)

## What's next

- Use the requested product type in retrieval (the largest remaining quality failure) and stop treating unstated concerns as the user's in the remaining cases.
- Add a triage rule for depigmentation and route makeup requests that mention skin as out of scope.
- A labeled photo set for the image path; a domain expert's review of ingredient claims.
- Merge the Sephora catalog and fix the haircare leak at the catalog level; swap in a managed vector store (e.g. Databricks Vector Search).
