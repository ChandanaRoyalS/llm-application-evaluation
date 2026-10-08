"""The two entry points the app and the evaluation both use.

run_pipeline(query, model)           -> text path
run_image_pipeline(image_path, ...)  -> photo path

Each returns a *trace*: a dict recording every step (detected concerns,
retrieved products, the exact context the LLM saw, its raw output, the
parsed answer, tokens, latency, cost, errors). The UI shows trace["answer"];
the evaluation scores the rest.
"""
import time

from . import catalog, config, generation, llm, retrieval, triage, vision

MSG_NOT_READY = ("⏳ The assistant is still warming up (loading the recommendation "
                 "engine). Please try again in about 30 seconds.")
MSG_STARTUP_FAILED = ("Sorry — the assistant couldn't start properly. "
                      "Please try again later.")
MSG_EMPTY = "Please tell me a bit about your skin and what you'd like help with."
MSG_NO_CONCERN = (
    "Hi! I'm a skincare assistant. Tell me about a skin concern — for example "
    "oily skin, breakouts, dryness, dark spots or fine lines — and I'll suggest "
    "products from our catalog.")
MSG_NO_PRODUCTS = ("I couldn't find products in our catalog for that concern. "
                   "Could you describe it a little differently?")
MSG_LLM_ERROR = ("Sorry — I'm having trouble reaching the recommendation model right "
                 "now. Please try again in a moment.")
MSG_ESCALATE = (
    "🩺 Based on what's visible in your photo, I'd recommend having this looked at "
    "by a dermatologist for a proper evaluation. I'm only able to offer cosmetic "
    "skincare guidance, so a professional is the right next step here.")
MSG_RETAKE = ("📸 I couldn't analyze your skin clearly from this photo. Could you "
              "share a clearer, well-lit photo of your face?")
MSG_NO_PHOTO = "Please upload a photo first."
MSG_MEDICAL = (
    "🩺 What you're describing should be checked by a doctor or dermatologist, so I "
    "won't suggest products for it. I can only help with cosmetic skincare. If you "
    "have swelling of the face, lips or throat, trouble breathing, or a rash that is "
    "spreading fast, feels hot or comes with a fever, please seek urgent medical care "
    "right away.")
MSG_OUT_OF_SCOPE = (
    "I can only help with skincare, so I can't recommend hair, makeup, fragrance or "
    "other products. If you have a skin concern — like oiliness, breakouts, dryness, "
    "dark spots or fine lines — tell me about it and I'll suggest something.")

MAX_QUERY_CHARS = 2000


def _new_trace(kind, model):
    return {
        "kind": kind, "model": model, "status": None, "answer": None,
        "detected_concerns": [], "concern_scores": [], "retrieved_product_ids": [],
        "context_given_to_llm": None, "raw_llm_output": None,
        "recommended_ids": None, "invalid_numbers": [], "parse_ok": None,
        "prompt_tokens": None, "completion_tokens": None,
        "llm_latency_ms": None, "total_latency_ms": None, "cost_usd": None,
        "error": None, "triage_route": None, "triage_reason": None, "triage_parse_ok": None,
        "triage_prompt_tokens": None, "triage_completion_tokens": None, "triage_latency_ms": None,
    }


def _not_ready(trace):
    if catalog.STATE["error"]:
        trace.update(status="startup_error", answer=MSG_STARTUP_FAILED,
                     error=catalog.STATE["error"])
    else:
        trace.update(status="not_ready", answer=MSG_NOT_READY)
    return trace


def _add_tokens(trace, prompt, completion):
    if prompt is not None:
        trace["prompt_tokens"] = (trace["prompt_tokens"] or 0) + prompt
    if completion is not None:
        trace["completion_tokens"] = (trace["completion_tokens"] or 0) + completion


def run_pipeline(query, model=None, temperature=None, use_triage=None):
    """Text path: triage -> detect concerns -> hybrid retrieve -> grounded structured answer.

    Token counts in the trace are totals (triage + generation); the triage share is
    also stored separately."""
    model = model or config.DEFAULT_TEXT_MODEL
    trace = _new_trace("text", model)
    trace["query"] = query
    start = time.perf_counter()

    try:
        if not catalog.is_ready():
            return _not_ready(trace)

        query = (query or "").strip()
        if not query:
            trace.update(status="empty_input", answer=MSG_EMPTY)
            return trace
        if len(query) > MAX_QUERY_CHARS:
            query = query[:MAX_QUERY_CHARS]
            trace["truncated"] = True

        if config.TRIAGE_ENABLED if use_triage is None else use_triage:
            try:
                t = triage.classify(query, config.TRIAGE_MODEL or model, temperature=0.0)
            except llm.LLMError as e:
                trace.update(status="llm_error", answer=MSG_LLM_ERROR, error=f"triage: {e}")
                return trace
            trace.update(triage_route=t["route"], triage_reason=t["reason"],
                         triage_parse_ok=t["parse_ok"], triage_prompt_tokens=t["prompt_tokens"],
                         triage_completion_tokens=t["completion_tokens"],
                         triage_latency_ms=t["latency_ms"])
            _add_tokens(trace, t["prompt_tokens"], t["completion_tokens"])
            if t["route"] == "medical":
                trace.update(status="escalated", answer=MSG_MEDICAL, recommended_ids=[])
                return trace
            if t["route"] == "out_of_scope":
                trace.update(status="out_of_scope", answer=MSG_OUT_OF_SCOPE, recommended_ids=[])
                return trace
            if t["route"] == "off_topic":
                trace.update(status="off_topic", answer=MSG_NO_CONCERN, recommended_ids=[])
                return trace

        concerns, scores = retrieval.detect_concerns(query)
        trace["detected_concerns"] = concerns
        trace["concern_scores"] = [(c, round(s, 4)) for c, s in scores]
        if not concerns:
            trace.update(status="no_concern", answer=MSG_NO_CONCERN)
            return trace

        product_ids = retrieval.retrieve(query, concerns)
        trace["retrieved_product_ids"] = product_ids
        if not product_ids:
            trace.update(status="no_products", answer=MSG_NO_PRODUCTS)
            return trace

        context_text, number_to_id = generation.build_context(product_ids)
        trace["context_given_to_llm"] = context_text
        messages = generation.build_messages(query, concerns, context_text)

        try:
            result = llm.chat(model, messages, max_tokens=500, temperature=temperature)
        except llm.LLMError as e:
            trace.update(status="llm_error", answer=MSG_LLM_ERROR, error=str(e))
            return trace

        trace.update(raw_llm_output=result["text"], llm_latency_ms=result["latency_ms"],
                     cost_usd=result["cost_usd"])
        _add_tokens(trace, result["prompt_tokens"], result["completion_tokens"])
        trace.update(generation.parse_response(result["text"], number_to_id))
        trace["status"] = "ok"
        return trace
    finally:
        trace["total_latency_ms"] = round((time.perf_counter() - start) * 1000)


def run_image_pipeline(image_path, vision_model=None, text_model=None, temperature=None):
    """Photo path: vision triage, then (for 'recommend') the text pipeline."""
    vision_model = vision_model or config.DEFAULT_VISION_MODEL
    trace = _new_trace("image", vision_model)
    trace.update(decision=None, image_concerns=[], observation=None,
                 vision_parse_ok=None, text_trace=None)
    start = time.perf_counter()

    try:
        if not catalog.is_ready():
            return _not_ready(trace)
        if image_path is None:
            trace.update(status="empty_input", answer=MSG_NO_PHOTO)
            return trace

        try:
            image_b64 = vision.encode_image(image_path)
        except Exception as e:
            trace.update(status="bad_image", answer=MSG_RETAKE, error=str(e))
            return trace

        try:
            result = llm.chat(vision_model, vision.build_messages(image_b64),
                              max_tokens=300, temperature=temperature)
        except llm.LLMError as e:
            trace.update(status="llm_error", answer=MSG_LLM_ERROR, error=str(e))
            return trace

        parsed = vision.parse_decision(result["text"])
        trace.update(raw_llm_output=result["text"], decision=parsed["decision"],
                     image_concerns=parsed["concerns"], observation=parsed["observation"],
                     vision_parse_ok=parsed["parse_ok"],
                     prompt_tokens=result["prompt_tokens"],
                     completion_tokens=result["completion_tokens"],
                     llm_latency_ms=result["latency_ms"], cost_usd=result["cost_usd"])

        header = f"**Image analysis:** {parsed['observation']}\n\n" if parsed["observation"] else ""
        if parsed["decision"] == "escalate":
            trace.update(status="ok", answer=header + MSG_ESCALATE)
        elif parsed["decision"] == "retake":
            trace.update(status="ok", answer=header + MSG_RETAKE)
        elif not parsed["concerns"]:
            trace.update(status="ok", answer=header + (
                "I couldn't detect a specific concern. Could you tell me what you'd "
                "like help with in the Chat tab?"))
        else:
            text_trace = run_pipeline("my skin shows " + " and ".join(parsed["concerns"]),
                                      model=text_model, temperature=temperature, use_triage=False)
            trace["text_trace"] = text_trace
            trace.update(status="ok", answer=(
                header + f"✨ I can see signs of: **{', '.join(parsed['concerns'])}**. "
                f"Here are some products that may help:\n\n{text_trace['answer']}"))
        return trace
    finally:
        trace["total_latency_ms"] = round((time.perf_counter() - start) * 1000)
