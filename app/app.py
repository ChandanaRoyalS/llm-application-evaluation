"""
Skincare Recommendation Assistant — Gradio UI (Hugging Face Spaces or Databricks Apps).

All logic lives in the `pipeline` package so the evaluation runs exactly the
same code as the live app. This file only builds the UI.
  1. Chat  — free-text skin concern -> hybrid RAG retrieval -> grounded LLM answer
  2. Photo — image upload -> vision three-mode analysis (recommend/escalate/retake)
"""
import logging
import os
import threading

# Exempt localhost from the container's proxy settings — without this,
# Gradio's launch self-check request to 127.0.0.1 gets intercepted by
# the proxy and fails with "localhost is not accessible".
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,0.0.0.0")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1,0.0.0.0")

import gradio as gr  # noqa: E402

import pipeline  # noqa: E402
import showcase  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

# Bind the web port first and load models in the background
# (Databricks Apps health-checks the port; heavy loading before launch
# risks the app being marked as crashed).
threading.Thread(target=pipeline.load, daemon=True).start()


def chat_fn(message, history):
    trace = pipeline.run_pipeline(message)
    log.info("text status=%s concerns=%s products=%s latency_ms=%s",
             trace["status"], trace["detected_concerns"],
             len(trace["retrieved_product_ids"]), trace["total_latency_ms"])
    return trace["answer"] + showcase.note(trace)


def image_fn(image_path):
    trace = pipeline.run_image_pipeline(image_path)
    log.info("image status=%s decision=%s latency_ms=%s",
             trace["status"], trace.get("decision"), trace["total_latency_ms"])
    return trace["answer"]


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

    with gr.Tab("📊 Evaluation explorer"):
        gr.Markdown(showcase.header())
        with gr.Row():
            cat_dd = gr.Dropdown([showcase.ALL] + list(showcase.CATEGORIES.values()),
                                 value=showcase.ALL, label="Category")
            res_dd = gr.Dropdown(showcase.RESULTS, value=showcase.RESULTS[0], label="Result")
        first = showcase.case_choices()
        case_dd = gr.Dropdown(first, value=first[0][1] if first else None,
                              label="Test case (✅ passed every check · ❌ failed at least one)")
        case_md = gr.Markdown(showcase.render_case(first[0][1]) if first else "")

        def _filter(cat, res):
            ch = showcase.case_choices(cat, res)
            val = ch[0][1] if ch else None
            return gr.update(choices=ch, value=val), showcase.render_case(val)

        cat_dd.change(_filter, [cat_dd, res_dd], [case_dd, case_md])
        res_dd.change(_filter, [cat_dd, res_dd], [case_dd, case_md])
        case_dd.change(showcase.render_case, case_dd, case_md)

    with gr.Tab("📷 Photo analysis"):
        gr.Markdown("Upload a clear, well-lit photo of your face. "
                    "The assistant describes visible cosmetic characteristics — "
                    "it never diagnoses medical conditions.\n\n"
                    "*Privacy: your photo is sent to a third-party AI model provider "
                    "(via Hugging Face Inference Providers) for analysis.*")
        img_in = gr.Image(type="filepath", label="Your photo")
        img_btn = gr.Button("Analyze")
        img_out = gr.Markdown()
        img_btn.click(fn=image_fn, inputs=img_in, outputs=img_out)

# Port: DATABRICKS_APP_PORT on Databricks, 7860 (Hugging Face default) elsewhere.
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0",
                server_port=int(os.environ.get("DATABRICKS_APP_PORT")
                                or os.environ.get("PORT", 7860)))
