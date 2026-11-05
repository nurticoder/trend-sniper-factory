"""Actual Moondream GPU inspection for the free Gradio host. No dummy GPU work."""

import io
import os

from PIL import Image

MODEL = "vikhyatk/moondream2"
REVISION = "9a7d4024050840e001defacec2b00727e89149e6"
verify_frame = None


def load():
    global verify_frame
    if os.environ.get("TSF_WORKER_PROCESS") != "1" or not os.environ.get("SPACE_ID"):
        raise ValueError("GPU vision setup is restricted to the remote Space")
    # Import spaces before Torch: its documented CUDA emulation loads model tensors
    # at startup and allocates a real GPU only around the decorated query.
    import spaces
    import torch
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        revision=REVISION,
        trust_remote_code=True,
        device_map={"": "cuda"},
    )

    @spaces.GPU(duration=15)
    def inspect_frame(jpeg, prompt):
        with Image.open(io.BytesIO(jpeg)) as image, torch.inference_mode():
            return model.query(image.convert("RGB"), prompt)["answer"]

    # Called by the durable worker, with no forwarded owner billing/inference token.
    # Free anonymous/IP quota refusal is a visible job failure, never a paid fallback.
    verify_frame = inspect_frame


def inspect(jpeg, prompt):
    if verify_frame is None:
        raise ValueError("Remote GPU vision was not initialized")
    try:
        return verify_frame(jpeg, prompt)
    except Exception as exc:
        raise ValueError(
            "Free GPU footage inspection unavailable or quota exhausted: "
            + str(exc)[:300]
        ) from exc
