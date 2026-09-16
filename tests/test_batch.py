from sqlalchemy import select

from app import db, service, worker


def test_batch_queued_null_payloads_are_not_business_duplicates(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(db, "DATA", tmp_path)
    engine = db.make_engine("sqlite:///" + str(tmp_path / "batch.db"))
    samples = json.loads((db.ROOT / "fixtures/catalog.json").read_text())[:3]
    with engine.begin() as conn:
        for sample in samples:
            conn.execute(db.orders.insert().values(**sample["order"]))
    for sample in samples:
        service.intake(engine, (db.ROOT / "fixtures" / sample["file"]).read_bytes(), sample["file"], "replay")
    while job := db.claim(engine, "batch-test"):
        worker.run_job(engine, job)
    with engine.connect() as conn:
        assert conn.execute(select(db.documents.c.status)).scalars().all() == ["needs_review"] * 3
    engine.dispose()
