"""Explicitly retry failed document extraction; never resets uncertain sync."""

from sqlalchemy import select

from app import db, service

engine = db.make_engine()
with engine.connect() as conn:
    rows = conn.execute(
        select(db.documents.c.id, db.documents.c.version).where(db.documents.c.status == "failed")
    ).all()
for doc_id, version in rows:
    service.mutate(engine, doc_id, version, "retry", "local operator")
print(f"Queued {len(rows)} failed extractions. Sync outcomes unchanged.")
