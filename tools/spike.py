"""Development-only feasibility run. Do not use this report as held-out accuracy."""

import json
import time

import httpx

from app import db, extraction

catalog = json.loads((db.ROOT / "fixtures" / "catalog.json").read_text())
results = []
output = db.ROOT / "docs" / "evidence"
output.mkdir(parents=True, exist_ok=True)
for attempt in range(120):
    try:
        if httpx.get("http://127.0.0.1:8091/v1/models", timeout=2).is_success:
            break
    except httpx.HTTPError:
        pass
    time.sleep(1)
else:
    raise RuntimeError("Start the local model before the feasibility run.")
for sample in [x for x in catalog if x["split"] == "development"][:10]:
    start = time.monotonic()
    record = {"file": sample["file"], "split": "development", "expected": sample["expected"]}
    try:
        text, lines, _ = extraction.read_document(
            db.ROOT / "fixtures" / sample["file"], db.DATA / "spike" / sample["file"]
        )
        payload, raw = extraction.extract_local(text)
        record.update(
            actual=payload,
            raw=raw,
            exact=payload == sample["expected"],
            evidence=extraction.locate_evidence(payload, lines),
        )
    except Exception as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)[:300]
    record["seconds"] = round(time.monotonic() - start, 2)
    results.append(record)
    print(sample["file"], record.get("exact", False), record["seconds"], record.get("error", ""), flush=True)
    (output / "local-model-spike.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
