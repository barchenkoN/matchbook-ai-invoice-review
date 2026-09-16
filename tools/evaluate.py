"""Frozen held-out pipeline evaluation with separate raw-model and hybrid metrics."""

import hashlib
import json
import statistics
import time
from decimal import Decimal

from app import db, extraction
from app.domain import validate_invoice


def canonical(payload):
    result = dict(payload)
    for field in ["subtotal", "tax", "total"]:
        result[field] = str(Decimal(str(result[field])).normalize())
    result["items"] = [
        dict(x, **{k: str(Decimal(str(x[k])).normalize()) for k in ["quantity", "unit_price", "line_total"]})
        for x in result["items"]
    ]
    return result


def main():
    catalog = json.loads((db.ROOT / "fixtures/catalog.json").read_text())
    samples = [x for x in catalog if x["split"] == "holdout"]
    output = db.ROOT / "docs/evidence"
    output.mkdir(parents=True, exist_ok=True)
    records = []
    prompt_hash = hashlib.sha256(
        (db.ROOT / "app/extraction.py").read_bytes() + (db.ROOT / "tools/model_server.py").read_bytes()
    ).hexdigest()
    for sample in samples:
        start = time.monotonic()
        record = {"file": sample["file"], "layout": sample["layout"], "expected": sample["expected"]}
        try:
            text, lines, _ = extraction.read_document(
                db.ROOT / "fixtures" / sample["file"], db.DATA / "evaluation" / sample["file"]
            )
            model, raw = extraction.extract_local(text)
            final, corrections = extraction.reconcile_explicit_source(model, lines)
            evidence = extraction.locate_evidence(final, lines)
            actual_issues = {x["code"] for x in validate_invoice(final, sample["order"], evidence)}
            expected_issues = {x["code"] for x in validate_invoice(sample["expected"], sample["order"])}
            record.update(
                raw_model=model,
                final=final,
                raw_response=raw,
                source_corrections=corrections,
                raw_exact=canonical(model) == canonical(sample["expected"]),
                final_exact=canonical(final) == canonical(sample["expected"]),
                expected_issues=sorted(expected_issues),
                actual_issues=sorted(actual_issues),
                unsafe_pass=bool(expected_issues and not actual_issues),
                evidence_fields=len(evidence),
            )
        except Exception as exc:
            record["error"] = type(exc).__name__
        record["seconds"] = round(time.monotonic() - start, 2)
        records.append(record)
        print(
            sample["file"],
            "raw=",
            record.get("raw_exact"),
            "pipeline=",
            record.get("final_exact"),
            record["seconds"],
            flush=True,
        )
        durations = sorted(x["seconds"] for x in records)
        summary = dict(
            corpus="Synthetic digital PDFs; two held-out layouts sharing a simple one-line table structure",
            planned=len(samples),
            completed=len(records),
            raw_exact=sum(x.get("raw_exact", False) for x in records),
            pipeline_exact=sum(x.get("final_exact", False) for x in records),
            unsafe_passes=sum(x.get("unsafe_pass", False) for x in records),
            errors=sum("error" in x for x in records),
            latency_p50=round(statistics.median(durations), 2),
            latency_p95=durations[min(len(durations) - 1, int(0.95 * len(durations)))],
            implementation_sha256=prompt_hash,
            model="Qwen3 0.6B Q8_0 GGUF dequantized to float32 in Transformers CPU",
            numeric_comparison="Decimal normalization; strings and item order exact",
        )
        (output / "heldout-evaluation.json").write_text(
            json.dumps({"summary": summary, "records": records}, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
