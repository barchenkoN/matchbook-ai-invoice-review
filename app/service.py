import hashlib
import time
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app import db
from app.domain import Invoice, validate_invoice


class Conflict(Exception):
    pass


def get_document(engine, document_id):
    with engine.connect() as conn:
        row = conn.execute(select(db.documents).where(db.documents.c.id == document_id)).mappings().first()
        if row is None:
            raise KeyError(document_id)
        result = dict(row)
        result.pop("path", None)
        payload = result.get("payload") or {}
        order = (
            conn.execute(select(db.orders).where(db.orders.c.id == payload.get("po_number", "")))
            .mappings()
            .first()
        )
        result["order"] = dict(order) if order else None
        result["events"] = [
            dict(e)
            for e in conn.execute(
                select(db.events)
                .where(db.events.c.document_id == document_id)
                .order_by(db.events.c.created.desc())
                .limit(50)
            ).mappings()
        ]
        result["revisions"] = [
            dict(r)
            for r in conn.execute(
                select(db.revisions)
                .where(db.revisions.c.document_id == document_id)
                .order_by(db.revisions.c.revision.desc())
                .limit(20)
            ).mappings()
        ]
        return result


def intake(engine, content, filename, mode="local", actor="reviewer"):
    suffix = Path(filename).suffix.lower()
    if suffix not in (".pdf", ".png", ".jpg", ".jpeg"):
        raise ValueError("Choose a PDF, PNG or JPEG file.")
    if not 0 < len(content) <= 10 * 1024 * 1024:
        raise ValueError("Upload a non-empty document up to 10 MB.")
    valid = (
        content.startswith(b"%PDF")
        if suffix == ".pdf"
        else (
            content.startswith(b"\x89PNG\r\n\x1a\n")
            if suffix == ".png"
            else content.startswith(b"\xff\xd8\xff")
        )
    )
    if not valid:
        raise ValueError("File contents do not match the supported document format.")
    digest = hashlib.sha256(content).hexdigest()
    with engine.connect() as conn:
        existing = conn.execute(select(db.documents.c.id).where(db.documents.c.sha256 == digest)).scalar()
    if existing:
        return existing, True
    doc_id = db.uid()
    folder = db.DATA / "documents" / doc_id
    folder.mkdir(parents=True)
    path = folder / ("original" + suffix)
    path.write_bytes(content)
    try:
        with engine.begin() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    sha256=digest,
                    filename=Path(filename).name[:200],
                    path=str(path),
                    status="queued",
                    mode=mode,
                    created=time.time(),
                    updated=time.time(),
                    version=1,
                    revision=0,
                    payload=None,
                    evidence={},
                    issues=[],
                    pages=0,
                )
            )
            db.enqueue(conn, doc_id, "extract")
            db.audit(
                conn, doc_id, "Document received", actor, "SHA-256 checked; queued for document processing."
            )
    except IntegrityError:
        path.unlink(missing_ok=True)
        with engine.connect() as conn:
            existing = conn.execute(select(db.documents.c.id).where(db.documents.c.sha256 == digest)).scalar()
        if existing:
            return existing, True
        raise
    return doc_id, False


def contextual_issues(conn, document_id, payload, evidence):
    order = (
        conn.execute(select(db.orders).where(db.orders.c.id == payload.get("po_number", "")))
        .mappings()
        .first()
    )
    issues = validate_invoice(payload, dict(order) if order else None, evidence)
    # Small bounded local portfolio dataset; predicate can become indexed business columns at scale.
    others = conn.execute(
        select(db.documents.c.payload, db.documents.c.status).where(
            db.documents.c.id != document_id, db.documents.c.payload.is_not(None)
        )
    ).mappings()
    for other in others:
        obj = other["payload"]
        if not isinstance(obj, dict):
            continue
        if (
            obj.get("supplier", "").strip().casefold() == payload.get("supplier", "").strip().casefold()
            and obj.get("invoice_number", "").strip().casefold()
            == payload.get("invoice_number", "").strip().casefold()
        ):
            issues.append(
                dict(
                    code="duplicate_invoice",
                    severity="blocking",
                    title="Invoice number already exists",
                    detail="Another document has the same supplier and invoice number. Resolve the duplicate outside this demo.",
                    field="invoice_number",
                    line=None,
                )
            )
        elif obj.get("po_number") == payload.get("po_number") and other["status"] in (
            "approved",
            "syncing",
            "synced",
            "sync_uncertain",
        ):
            issues.append(
                dict(
                    code="repeat_billing",
                    severity="blocking",
                    title="Order already allocated",
                    detail="This demo blocks further billing against an allocated receipt.",
                    field="po_number",
                    line=None,
                )
            )
    return issues


def mutate(engine, document_id, version, action, actor, payload=None):
    with engine.begin() as conn:
        row = conn.execute(select(db.documents).where(db.documents.c.id == document_id)).mappings().first()
        if row is None:
            raise KeyError(document_id)
        if row["version"] != version:
            raise Conflict(
                "This invoice changed in another session. Refresh before continuing; your edits are still available."
            )
        updates = {"version": version + 1, "updated": time.time()}
        if action == "edit":
            if row["status"] not in ("needs_review", "approved"):
                raise Conflict("This invoice cannot be edited in its current state.")
            payload = Invoice.model_validate(payload).model_dump(mode="json")
            evidence = dict(row["evidence"] or {})
            old = row["payload"] or {}
            for key, value in payload.items():
                if value != old.get(key):
                    if key == "items":
                        for i, line in enumerate(value):
                            for field in line:
                                evidence[f"items.{i}.{field}"] = {
                                    "manual": True,
                                    "text": "Reviewer-verified value",
                                    "page": 1,
                                }
                    else:
                        evidence[key] = {"manual": True, "text": "Reviewer-verified value", "page": 1}
            # Saving explicitly verifies previously unsupported source fields without falsifying coordinates.
            for key in [
                "supplier",
                "invoice_number",
                "invoice_date",
                "currency",
                "po_number",
                "subtotal",
                "tax",
                "total",
            ]:
                evidence.setdefault(key, {"manual": True, "text": "Reviewer-verified value", "page": 1})
            for i, line in enumerate(payload["items"]):
                for key in line:
                    evidence.setdefault(
                        f"items.{i}.{key}", {"manual": True, "text": "Reviewer-verified value", "page": 1}
                    )
            revision = row["revision"] + 1
            conn.execute(delete(db.allocations).where(db.allocations.c.document_id == document_id))
            updates.update(
                payload=payload,
                evidence=evidence,
                revision=revision,
                status="needs_review",
                approved_by=None,
                issues=contextual_issues(conn, document_id, payload, evidence),
            )
            conn.execute(
                db.revisions.insert().values(
                    id=db.uid(),
                    document_id=document_id,
                    revision=revision,
                    payload=payload,
                    actor=actor,
                    created=time.time(),
                )
            )
            db.audit(
                conn,
                document_id,
                "Verified revision saved",
                actor,
                f"Revision {revision}; prior approval invalidated. Manual fields identified separately.",
            )
        elif action == "approve":
            if row["status"] != "needs_review":
                raise Conflict("Only an invoice awaiting review can be approved.")
            issues = contextual_issues(conn, document_id, row["payload"], row["evidence"])
            if issues:
                raise Conflict("Resolve all blocking discrepancies before approval.")
            updates.update(status="approved", approved_by=actor, issues=[])
            # Unique order allocation serializes approval across different invoice rows too.
            try:
                with conn.begin_nested():
                    conn.execute(
                        db.allocations.insert().values(
                            order_id=row["payload"]["po_number"], document_id=document_id
                        )
                    )
            except IntegrityError:
                raise Conflict(
                    "Another invoice has already allocated this order. Further billing is unsupported in this version."
                ) from None
            db.audit(
                conn, document_id, "Invoice approved", actor, f"Approval bound to revision {row['revision']}."
            )
        elif action == "sync":
            if row["status"] != "approved":
                raise Conflict("Approve the current revision before creating a draft.")
            if contextual_issues(conn, document_id, row["payload"], row["evidence"]):
                raise Conflict("Order or duplicate checks changed. Review this invoice again.")
            reference = f"mb-{document_id}-r{row['revision']}"
            conn.execute(
                db.syncs.insert().values(
                    reference=reference,
                    document_id=document_id,
                    revision=row["revision"],
                    state="queued",
                    payload=row["payload"],
                    created=time.time(),
                )
            )
            db.enqueue(conn, document_id, "sync")
            updates.update(status="syncing", error=None)
            db.audit(
                conn,
                document_id,
                "Draft creation queued",
                actor,
                "Confirmed destination; worker will create a draft only.",
            )
        elif action == "retry":
            if row["status"] != "failed":
                raise Conflict(
                    "Only failed extraction can be retried. Uncertain sync requires reconciliation."
                )
            updates.update(status="queued", error=None)
            db.enqueue(conn, document_id, "extract")
            db.audit(conn, document_id, "Extraction retried", actor)
        else:
            raise ValueError("Unknown action.")
        result = conn.execute(
            update(db.documents)
            .where(db.documents.c.id == document_id, db.documents.c.version == version)
            .values(**updates)
        )
        if result.rowcount != 1:
            raise Conflict("Concurrent update rejected. Refresh and review the current version.")
    return get_document(engine, document_id)


def queue(engine, search="", status="", page=1, page_size=8):
    predicate = []
    if status:
        predicate.append(db.documents.c.status == status)
    if search:
        # JSON rendering supports a small portable search without treating input as SQL.
        from sqlalchemy import String, cast, or_

        pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        predicate.append(
            or_(
                db.documents.c.filename.ilike(pattern, escape="\\"),
                cast(db.documents.c.payload, String).ilike(pattern, escape="\\"),
            )
        )
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(db.documents).where(*predicate)).scalar()
        page = max(1, min(page, max(1, (total + page_size - 1) // page_size)))
        rows = (
            conn.execute(
                select(db.documents)
                .where(*predicate)
                .order_by(db.documents.c.created.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .mappings()
            .all()
        )
        counts = dict(
            conn.execute(select(db.documents.c.status, func.count()).group_by(db.documents.c.status)).all()
        )
        result = []
        for row in rows:
            obj = dict(row)
            for key in ("path", "text", "evidence"):
                obj.pop(key, None)
            result.append(obj)
    return dict(items=result, total=total, page=page, page_size=page_size, counts=counts)
