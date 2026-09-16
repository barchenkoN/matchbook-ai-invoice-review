"""Optional local Transformers CPU server. No vendor key, remote code or GPU dependency.

Unlike llama.cpp grammar decoding, this backend validates JSON after generation.
Do not claim constrained decoding for this adapter.
"""

import json
import os
import threading
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "runtime" / "qwen3-transformers"
torch.set_num_threads(6)
print("Loading local Qwen3 0.6B on CPU...", flush=True)
tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(
    path,
    gguf_file=str(ROOT / "runtime" / "qwen3-0.6b-q8.gguf"),
    dtype=torch.float32,
    local_files_only=True,
)
model.eval()
lock = threading.Lock()
app = FastAPI(docs_url=None, redoc_url=None)


@app.get("/v1/models")
def models():
    return {"data": [{"id": "Qwen3-0.6B-Transformers-CPU", "object": "model"}]}


@app.post("/v1/chat/completions")
def completion(body: dict):
    if not lock.acquire(blocking=False):
        raise HTTPException(429, "Local model busy. One document at a time.")
    try:
        messages = list(body["messages"])
        # Explicit example shape improves small-model adherence; no fixture facts are provided.
        shape = {
            "supplier": "Seller name",
            "invoice_number": "number",
            "invoice_date": "YYYY-MM-DD",
            "currency": "EUR",
            "po_number": "PO number",
            "subtotal": "0.00",
            "tax": "0.00",
            "total": "0.00",
            "items": [
                {
                    "sku": "code",
                    "description": "item name",
                    "quantity": "1",
                    "unit_price": "0.00",
                    "line_total": "0.00",
                }
            ],
        }
        messages[0] = dict(
            messages[0],
            content=messages[0]["content"] + "\nUse exactly these keys and types: " + json.dumps(shape),
        )
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        inputs = tokenizer(prompt, return_tensors="pt")
        if inputs.input_ids.shape[1] > 3500:
            raise HTTPException(422, "Document exceeds local model context policy.")
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=min(body.get("max_tokens", 1200), 1800),
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        content = tokenizer.decode(
            generated[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
        ).strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return {
            "model": "Qwen3-0.6B-Transformers-CPU",
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {
                "prompt_tokens": inputs.input_ids.shape[1],
                "completion_tokens": generated.shape[1] - inputs.input_ids.shape[1],
            },
        }
    finally:
        lock.release()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("MODEL_PORT", "8091")))
