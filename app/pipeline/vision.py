"""Photo path: three-mode vision triage (recommend / escalate / retake)."""
import base64
import io

from . import generation

VISION_PROMPT = """You are a cosmetic skin-image assistant. Look at the photo and decide ONE of:
1. 'recommend' - you see normal COSMETIC characteristics (oiliness, dryness, redness, dark spots, dullness, texture, large pores, fine lines).
2. 'escalate' - you see signs BEYOND cosmetic scope (significant inflammation, lesions, wounds, or anything unusual/concerning). Do NOT name any condition.
3. 'retake' - the photo is unusable (blurry, too dark, or no face/skin visible).

Reply ONLY with JSON in this exact format, nothing else:
{"decision": "recommend or escalate or retake", "concerns": ["list", "of", "cosmetic", "concern", "words"], "observation": "one short sentence describing what you see"}

Remember: describe only, never diagnose a medical condition."""

VALID_DECISIONS = {"recommend", "escalate", "retake"}


def encode_image(image_path, max_side=1024):
    """Normalize any upload (PNG, webp, screenshot...) to an RGB JPEG, base64."""
    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def build_messages(image_b64):
    return [{"role": "user", "content": [
        {"type": "text", "text": VISION_PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
    ]}]


def parse_decision(raw_text):
    """Returns dict(decision, concerns, observation, parse_ok).

    Unparseable or invalid output falls back to 'retake' — asking for a new
    photo is the safe default — and is flagged parse_ok=False.
    """
    obj = generation._extract_json_object(raw_text)
    if not isinstance(obj, dict):
        return {"decision": "retake", "concerns": [],
                "observation": "Could not analyze the image clearly.", "parse_ok": False}
    decision = str(obj.get("decision", "")).strip().lower()
    concerns = obj.get("concerns") or []
    if not isinstance(concerns, list):
        concerns = [str(concerns)]
    concerns = [str(c).strip() for c in concerns if str(c).strip()]
    if decision not in VALID_DECISIONS:
        return {"decision": "retake", "concerns": concerns,
                "observation": str(obj.get("observation", "")), "parse_ok": False}
    return {"decision": decision, "concerns": concerns,
            "observation": str(obj.get("observation", "")), "parse_ok": True}
