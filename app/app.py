"""
Skincare Recommendation Chatbot — Databricks App
Gradio interface with two tabs:
  1. Chat  — free-text skin concern -> hybrid RAG retrieval -> grounded LLM answer
  2. Photo — image upload -> vision three-mode analysis (recommend/escalate/retake)
"""
import os
# Exempt localhost from the container's proxy settings — without this,
# Gradio's launch self-check request to 127.0.0.1 gets intercepted by
# the proxy and fails with "localhost is not accessible".
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,0.0.0.0")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1,0.0.0.0")

import json
import base64

import gradio as gr
from sentence_transformers import SentenceTransformer
import chromadb
from numpy import dot
from numpy.linalg import norm
from databricks.sdk import WorkspaceClient

# ------------------------------------------------------------------
# Startup: load bundled catalog, embed, build vector store
# ------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------
# Lazy startup: bind the web port FIRST, load models in background.
# (Databricks Apps health-checks the port; heavy loading before
# launch risks being marked crashed.)
# ------------------------------------------------------------------
import threading

STATE = {"ready": False, "error": None}
model = None
collection = None
PRODUCTS = []
ID_TO_INGREDIENTS = {}
ALL_CONCERNS = []
CONCERN_EMBEDDINGS = None

TEXT_MODEL = "databricks-meta-llama-3-1-8b-instruct"
VISION_MODEL = "databricks-llama-4-maverick"

from openai import OpenAI

_workspace = None

def _get_llm_client():
    """Version-safe OpenAI client for Databricks model serving.
    Builds the client from the SDK's auth config (works across
    databricks-sdk versions, refreshes tokens automatically)."""
    global _workspace
    if _workspace is None:
        _workspace = WorkspaceClient()
    headers = _workspace.config.authenticate()
    token = headers["Authorization"].split(" ", 1)[1]
    return OpenAI(api_key=token,
                  base_url=f"{_workspace.config.host}/serving-endpoints")


def _load_everything():
    global model, collection, PRODUCTS, ID_TO_INGREDIENTS
    global ALL_CONCERNS, CONCERN_EMBEDDINGS
    try:
        with open(os.path.join(HERE, "app_data.json")) as f:
            PRODUCTS[:] = json.load(f)
        print(f"Loaded {len(PRODUCTS)} products")

        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode([p["document"] for p in PRODUCTS])

        chroma_client = chromadb.Client()
        collection = chroma_client.create_collection("skincare_products")
        collection.add(
            ids=[p["product_id"] for p in PRODUCTS],
            embeddings=[e.tolist() for e in embeddings],
            documents=[p["document"] for p in PRODUCTS],
            metadatas=[{"brand": p["brand"], "price": p["price"],
                        "concerns": ", ".join(p["concerns"])} for p in PRODUCTS])

        ID_TO_INGREDIENTS.update({p["product_id"]: p["ingredients"] for p in PRODUCTS})

        ALL_CONCERNS[:] = sorted({c for p in PRODUCTS for c in p["concerns"]})
        CONCERN_EMBEDDINGS = model.encode(ALL_CONCERNS)

        STATE["ready"] = True
        print("Startup complete — app ready.")
    except Exception as e:
        STATE["error"] = str(e)
        print("STARTUP ERROR:", e)


threading.Thread(target=_load_everything, daemon=True).start()


def _not_ready_msg():
    if STATE["error"]:
        return f"Startup error: {STATE['error']}"
    return ("⏳ The assistant is still warming up (loading the recommendation "
            "engine). Please try again in ~30 seconds.")

# ------------------------------------------------------------------
# Retrieval + generation
# ------------------------------------------------------------------
def detect_concerns(query_text, top_k=3, threshold=0.45):
    q_emb = model.encode([query_text])[0]
    scores = []
    for concern, c_emb in zip(ALL_CONCERNS, CONCERN_EMBEDDINGS):
        cos = dot(q_emb, c_emb) / (norm(q_emb) * norm(c_emb))
        scores.append((concern, float(cos)))
    scores.sort(key=lambda x: -x[1])
    matched = [c for c, s in scores[:top_k] if s >= threshold]
    return matched if matched else [scores[0][0]]


SYSTEM_PROMPT = (
    "You are a knowledgeable, friendly skincare assistant. Follow these rules strictly:\n"
    "1. Recommend ONLY products from the provided list. Never invent products.\n"
    "2. When explaining why a product helps, refer ONLY to the ingredients and "
    "concerns actually listed for that product. Do NOT invent ingredients, "
    "benefits, claims, or product links.\n"
    "3. Address ONLY the concerns the user actually mentioned. Do NOT assume other concerns.\n"
    "4. Keep a warm but professional tone. No pet names.\n"
    "5. Give cosmetic guidance only. Do NOT diagnose medical conditions. If the "
    "concern sounds severe or medical, gently suggest seeing a dermatologist."
)


def ask_skincare_bot(query_text, n=5):
    if not STATE["ready"]:
        return _not_ready_msg()
    detected = detect_concerns(query_text)

    query_embedding = model.encode([query_text])[0].tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=30)
    matched = []
    for i in range(len(results["ids"][0])):
        pid = results["ids"][0][i]
        meta = results["metadatas"][0][i]
        pc = [c.strip() for c in meta["concerns"].split(",") if c.strip()]
        if any(c in pc for c in detected):
            matched.append((pid, meta))
        if len(matched) >= n:
            break

    if not matched:
        return ("I couldn't find products in our catalog matching that concern. "
                "Could you describe it differently?")

    products_text = ""
    for i, (pid, p) in enumerate(matched, 1):
        ings = ", ".join(ID_TO_INGREDIENTS.get(pid, [])[:8])
        products_text += (f"{i}. {p['brand']} (${p['price']:.0f})\n"
                          f"   Treats: {p['concerns']}\n"
                          f"   Ingredients: {ings}\n")

    user_prompt = (
        f'User\'s message: "{query_text}"\n\n'
        f"The user's concern(s): {', '.join(detected)}\n\n"
        f"Products from our catalog (use ONLY these, and only their listed ingredients):\n"
        f"{products_text}\n"
        f"Write a warm, professional recommendation. Mention specific ingredients "
        f"from the list to explain why each product helps with the user's concern.")

    response = _get_llm_client().chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_prompt}],
        max_tokens=400)
    return response.choices[0].message.content


# ------------------------------------------------------------------
# Image path — three-mode vision analysis
# ------------------------------------------------------------------
VISION_PROMPT = """You are a cosmetic skin-image assistant. Look at the photo and decide ONE of:
1. 'recommend' - you see normal COSMETIC characteristics (oiliness, dryness, redness, dark spots, dullness, texture, large pores, fine lines).
2. 'escalate' - you see signs BEYOND cosmetic scope (significant inflammation, lesions, wounds, or anything unusual/concerning). Do NOT name any condition.
3. 'retake' - the photo is unusable (blurry, too dark, or no face/skin visible).

Reply ONLY with JSON in this exact format, nothing else:
{"decision": "recommend or escalate or retake", "concerns": ["list", "of", "cosmetic", "concern", "words"], "observation": "one short sentence describing what you see"}

Remember: describe only, never diagnose a medical condition."""


def handle_skin_image(image_path):
    if not STATE["ready"]:
        return _not_ready_msg()
    if image_path is None:
        return "Please upload a photo first."

    # Normalize the upload: whatever format the user gives (PNG, webp,
    # screenshot...), convert to a real RGB JPEG and cap the size —
    # the endpoint validates bytes against the declared image type.
    from PIL import Image
    import io
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    image_data = base64.b64encode(buf.getvalue()).decode("utf-8")

    completion = _get_llm_client().chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": VISION_PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}]
        }],
        max_tokens=300)

    raw = completion.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        result = json.loads(raw)
    except Exception:
        result = {"decision": "retake", "concerns": [],
                  "observation": "Could not analyze the image clearly."}

    decision = result.get("decision")
    concerns = result.get("concerns", [])
    observation = result.get("observation", "")

    header = f"**Image analysis:** {observation}\n\n"

    if decision == "escalate":
        return header + (
            "🩺 Based on what's visible in your photo, I'd recommend having this "
            "looked at by a dermatologist for a proper evaluation. I'm only able "
            "to offer cosmetic skincare guidance, so a professional is the right "
            "next step here.")
    if decision == "retake":
        return header + (
            "📸 I couldn't analyze your skin clearly from this photo. Could you "
            "share a clearer, well-lit photo of your face?")
    if decision == "recommend":
        if not concerns:
            return header + ("I couldn't detect a specific concern. Could you tell "
                             "me what you'd like help with in the Chat tab?")
        reco = ask_skincare_bot("my skin shows " + " and ".join(concerns))
        return (header + f"✨ I can see signs of: **{', '.join(concerns)}**. "
                f"Here are some products that may help:\n\n{reco}")
    return "Something went wrong analyzing the image. Please try again."


# ------------------------------------------------------------------
# Gradio UI
# ------------------------------------------------------------------
def chat_fn(message, history):
    return ask_skincare_bot(message)


with gr.Blocks(title="Skincare Assistant") as demo:
    gr.Markdown("# 🧴 Skincare Recommendation Assistant")
    gr.Markdown("*Cosmetic guidance only — not medical advice. For anything that "
                "looks serious, please see a dermatologist.*")

    with gr.Tab("💬 Chat"):
        gr.ChatInterface(
            fn=chat_fn,
            examples=["my skin is really oily and I keep getting breakouts",
                      "I have dark spots and uneven skin tone",
                      "my skin is dry and flaky"],
        )

    with gr.Tab("📷 Photo analysis"):
        gr.Markdown("Upload a clear, well-lit photo of your face. "
                    "The assistant describes visible cosmetic characteristics — "
                    "it never diagnoses medical conditions.")
        img_in = gr.Image(type="filepath", label="Your photo")
        img_btn = gr.Button("Analyze")
        img_out = gr.Markdown()
        img_btn.click(fn=handle_skin_image, inputs=img_in, outputs=img_out)

# Native Gradio serving. (The FastAPI mount produced 307 redirects
# built with the internal "localhost" host behind Databricks' proxy;
# with NO_PROXY set above, launch()'s self-check passes and Gradio
# serves directly with no redirects.)
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0",
                server_port=int(os.environ.get("DATABRICKS_APP_PORT", 8000)))
