"""Run `python -m app.worker`; survives browser closes and recovers expired leases."""

import json
import time
from pathlib import Path

from sqlalchemy import select, update

from app import db, erp, extraction, service


def run_job(engine, job):
    doc_id = job["document_id"]
    start = time.monotonic()
    with engine.begin() as conn:
        doc = dict(conn.execute(select(db.documents).where(db.documents.c.id == doc_id)).mappings().one())
        if job["kind"] == "extract":
            conn.execute(
                update(db.documents)
                .where(db.documents.c.id == doc_id)
                .values(status="processing", version=db.documents.c.version + 1)
            )
            db.audit(
                conn,
                doc_id,
                "Extraction started",
                detail="Local document parsing; " + doc["mode"] + " extraction mode.",
            )
    try:
        if job["kind"] == "extract":
            text, lines, pages = extraction.read_document(doc["path"], Path(doc["path"]).parent / "pages")
            with engine.begin() as conn:
                if not owns(conn, job):
                    return
                conn.execute(
                    update(db.documents)
                    .where(db.documents.c.id == doc_id)
                    .values(text=text, pages=pages, updated=time.time())
                )
            if doc["mode"] == "replay":
                catalog = json.loads((db.ROOT / "fixtures" / "catalog.json").read_text(encoding="utf-8"))
                sample = next((x for x in catalog if x["sha256"] == doc["sha256"]), None)
                if sample is None:
                    raise ValueError(
                        "Replay supports only the included examples. Choose local AI for a new document."
                    )
                payload = sample["expected"]
                raw = {"mode": "replay", "note": "Synthetic reference data; not model inference."}
            else:
                payload, raw = extraction.extract_local(text)
                payload, corrections = extraction.reconcile_explicit_source(payload, lines)
                raw["source_corrections"] = corrections
            evidence = extraction.locate_evidence(payload, lines)
            Path(doc["path"]).with_name("extraction.json").write_text(
                json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            with engine.begin() as conn:
                if not owns(conn, job):
                    return
                issues = service.contextual_issues(conn, doc_id, payload, evidence)
                conn.execute(
                    update(db.documents)
                    .where(db.documents.c.id == doc_id)
                    .values(
                        status="needs_review",
                        revision=1,
                        version=db.documents.c.version + 1,
                        payload=payload,
                        evidence=evidence,
                        issues=issues,
                        text=text,
                        pages=pages,
                        elapsed=round(time.monotonic() - start, 3),
                        source_engine="recorded fixture"
                        if doc["mode"] == "replay"
                        else "local model / OpenAI-compatible endpoint",
                        error=None,
                        updated=time.time(),
                    )
                )
                conn.execute(
                    db.revisions.insert().values(
                        id=db.uid(),
                        document_id=doc_id,
                        revision=1,
                        payload=payload,
                        actor="extraction:" + doc["mode"],
                        created=time.time(),
                    )
                )
                db.audit(
                    conn,
                    doc_id,
                    "Three-way check completed",
                    detail=f"{len(issues)} blocking discrepancies. Source evidence preserved.",
                )
                if doc["mode"] == "local" and raw.get("source_corrections"):
                    db.audit(
                        conn,
                        doc_id,
                        "Model candidates reconciled with printed values",
                        detail=f"{len(raw['source_corrections'])} numeric fields corrected from unambiguous source text. Raw model output retained.",
                    )
        else:
            reference = f"mb-{doc_id}-r{doc['revision']}"
            with engine.begin() as conn:
                if not owns(conn, job):
                    return
                conn.execute(
                    update(db.syncs).where(db.syncs.c.reference == reference).values(state="dispatching")
                )
            name = erp.create_draft(engine, reference, doc["payload"])
            with engine.begin() as conn:
                if not owns(conn, job):
                    return
                conn.execute(
                    update(db.documents)
                    .where(db.documents.c.id == doc_id)
                    .values(
                        status="synced",
                        remote_id=name,
                        version=db.documents.c.version + 1,
                        updated=time.time(),
                        error=None,
                    )
                )
                conn.execute(
                    update(db.syncs)
                    .where(db.syncs.c.reference == reference)
                    .values(state="synced", remote_id=name)
                )
                db.audit(
                    conn,
                    doc_id,
                    "Draft created",
                    detail=f"{erp.mode()} destination: {name}. No posting or payment.",
                )
        with engine.begin() as conn:
            conn.execute(
                update(db.jobs)
                .where(db.jobs.c.id == job["id"], db.jobs.c.owner == job["owner"])
                .values(state="done", lease_until=0)
            )
    except Exception as exc:
        # Error messages deliberately exclude third-party response bodies, secrets and local paths.
        message = (
            str(exc)
            if isinstance(exc, ValueError) and "validation error" not in str(exc).lower()
            else "Processing failed. Check local services and the document, then retry."
        )
        message = message[:400]
        with engine.begin() as conn:
            if not owns(conn, job):
                return
            status = "sync_uncertain" if job["kind"] == "sync" else "failed"
            if status == "sync_uncertain":
                message = "The remote write outcome is unknown. Reconcile before attempting another action."
            conn.execute(
                update(db.documents)
                .where(db.documents.c.id == doc_id)
                .values(status=status, error=message, version=db.documents.c.version + 1, updated=time.time())
            )
            conn.execute(
                update(db.jobs)
                .where(db.jobs.c.id == job["id"])
                .values(
                    state="uncertain" if job["kind"] == "sync" else "failed",
                    error=type(exc).__name__,
                    lease_until=0,
                )
            )
            db.audit(conn, doc_id, "Processing requires attention", detail=message)


def owns(conn, job):
    return (
        conn.execute(
            select(db.jobs.c.id).where(
                db.jobs.c.id == job["id"],
                db.jobs.c.state == "running",
                db.jobs.c.owner == job["owner"],
                db.jobs.c.lease_until > time.time(),
            )
        ).scalar()
        is not None
    )


def main():
    engine = db.make_engine()
    owner = db.uid()
    with engine.begin() as conn:
        conn.execute(db.heartbeats.insert().values(id=owner, seen=time.time()))
    print("Matchbook worker ready", flush=True)
    while True:
        with engine.begin() as conn:
            conn.execute(update(db.heartbeats).where(db.heartbeats.c.id == owner).values(seen=time.time()))
        db.recover(engine)
        job = db.claim(engine, owner)
        if job:
            run_job(engine, job)
        else:
            time.sleep(0.7)


if __name__ == "__main__":
    main()
