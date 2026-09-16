import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import db, erp, extraction, service, worker
from app.domain import validate_invoice
from app.main import create_app


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA", tmp_path)
    monkeypatch.setenv("ERP_MODE", "sandbox")
    monkeypatch.setenv("MATCHBOOK_DEMO_AUTH", "1")
    engine = db.make_engine("sqlite:///" + str(tmp_path / "test.db"))
    samples = json.loads((db.ROOT / "fixtures" / "catalog.json").read_text())
    with engine.begin() as conn:
        for sample in samples:
            conn.execute(db.orders.insert().values(**sample["order"]))
    yield engine, samples
    engine.dispose()


def import_sample(env, index=1):
    engine, samples = env
    sample = samples[index]
    path = db.ROOT / "fixtures" / sample["file"]
    doc_id, _ = service.intake(engine, path.read_bytes(), path.name, "replay")
    job = db.claim(engine, "test")
    assert job
    worker.run_job(engine, job)
    return service.get_document(engine, doc_id)


def test_happy_path_durable_draft_readback(env):
    engine, _ = env
    doc = import_sample(env)
    assert doc["status"] == "needs_review" and not doc["issues"]
    assert doc["evidence"]["total"]["box"]
    doc = service.mutate(engine, doc["id"], doc["version"], "approve", "reviewer")
    doc = service.mutate(engine, doc["id"], doc["version"], "sync", "reviewer")
    worker.run_job(engine, db.claim(engine, "test"))
    doc = service.get_document(engine, doc["id"])
    assert doc["status"] == "synced" and doc["remote_id"].startswith("DEMO-PI")
    reference = f"mb-{doc['id']}-r{doc['revision']}"
    assert erp.reconcile(engine, reference) == doc["remote_id"]
    assert erp.create_draft(engine, reference, doc["payload"]) == doc["remote_id"]
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(db.sandbox_drafts)).scalar() == 1


def test_real_quantity_and_price_exceptions(env):
    doc = import_sample(env, 0)
    codes = {x["code"] for x in doc["issues"]}
    assert {"quantity", "price"} <= codes
    with pytest.raises(service.Conflict, match="blocking"):
        service.mutate(env[0], doc["id"], doc["version"], "approve", "reviewer")


def test_duplicate_upload_is_same_document(env):
    engine, samples = env
    sample = samples[1]
    content = (db.ROOT / "fixtures" / sample["file"]).read_bytes()
    first, _ = service.intake(engine, content, sample["file"], "replay")
    second, duplicate = service.intake(engine, content, "renamed.pdf", "replay")
    assert first == second and duplicate


def test_revision_invalidates_approval_and_stale_write_rejected(env):
    engine, _ = env
    doc = import_sample(env)
    approved = service.mutate(engine, doc["id"], doc["version"], "approve", "reviewer")
    changed = service.mutate(engine, doc["id"], approved["version"], "edit", "reviewer", approved["payload"])
    assert changed["status"] == "needs_review" and changed["approved_by"] is None
    assert changed["revision"] == 2 and len(changed["revisions"]) == 2
    with pytest.raises(service.Conflict):
        service.mutate(engine, doc["id"], approved["version"], "sync", "reviewer")


def test_two_reviewers_only_one_approval(env):
    engine, _ = env
    doc = import_sample(env)

    def approve():
        try:
            service.mutate(engine, doc["id"], doc["version"], "approve", "reviewer")
            return True
        except service.Conflict:
            return False

    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(lambda _: approve(), range(2))) == 1


def test_expired_extraction_lease_requeued(env):
    engine, samples = env
    sample = samples[1]
    doc_id, _ = service.intake(
        engine, (db.ROOT / "fixtures" / sample["file"]).read_bytes(), sample["file"], "replay"
    )
    job = db.claim(engine, "dead-worker", lease=-1)
    db.recover(engine)
    new = db.claim(engine, "replacement")
    assert new["id"] == job["id"] and new["owner"] == "replacement"
    worker.run_job(engine, new)
    assert service.get_document(engine, doc_id)["status"] == "needs_review"


def test_expired_sync_does_not_repeat_side_effect(env):
    engine, _ = env
    doc = import_sample(env)
    doc = service.mutate(engine, doc["id"], doc["version"], "approve", "reviewer")
    doc = service.mutate(engine, doc["id"], doc["version"], "sync", "reviewer")
    db.claim(engine, "interrupted", lease=-1)
    db.recover(engine)
    assert db.claim(engine, "replacement") is None
    assert service.get_document(engine, doc["id"])["status"] == "sync_uncertain"


def test_timeout_after_remote_commit_reconciles_without_second_draft(env, monkeypatch):
    engine, _ = env
    doc = import_sample(env)
    doc = service.mutate(engine, doc["id"], doc["version"], "approve", "reviewer")
    doc = service.mutate(engine, doc["id"], doc["version"], "sync", "reviewer")
    original = erp.create_draft

    def timeout(*args):
        original(*args)
        raise TimeoutError("simulated response loss after commit")

    monkeypatch.setattr(erp, "create_draft", timeout)
    worker.run_job(engine, db.claim(engine, "test"))
    current = service.get_document(engine, doc["id"])
    assert current["status"] == "sync_uncertain"
    with TestClient(create_app(engine)) as client:
        client.post("/api/login", json={"role": "reviewer"})
        response = client.post(f"/api/invoices/{doc['id']}/reconcile", json={"version": current["version"]})
        assert response.status_code == 200
        assert response.json()["status"] == "synced"
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(db.sandbox_drafts)).scalar() == 1


def test_viewer_and_anonymous_cannot_mutate(env):
    with TestClient(create_app(env[0])) as client:
        assert client.get("/api/invoices").status_code == 401
        client.post("/api/login", json={"role": "viewer"})
        assert client.get("/api/invoices").status_code == 200
        assert client.post("/api/invoices/no/actions/approve", json={"version": 1}).status_code == 403
        assert (
            client.post(
                "/api/login", json={"role": "reviewer"}, headers={"Origin": "https://untrusted.example"}
            ).status_code
            == 403
        )


def test_non_demo_auth_rejects_empty_password(env, monkeypatch):
    monkeypatch.setenv("MATCHBOOK_DEMO_AUTH", "0")
    monkeypatch.setenv("MATCHBOOK_REVIEWER_PASSWORD", "local-test-secret")
    with TestClient(create_app(env[0])) as client:
        assert client.post("/api/login", json={"role": "reviewer"}).status_code == 401
        assert (
            client.post("/api/login", json={"role": "reviewer", "password": "local-test-secret"}).status_code
            == 200
        )


@pytest.mark.parametrize(
    "content,name",
    [(b"<script>", "invoice.pdf"), (b"hello", "invoice.png"), (b"", "empty.pdf"), (b"fake", "a.exe")],
)
def test_unsupported_files_rejected(env, content, name):
    with pytest.raises(ValueError):
        service.intake(env[0], content, name)


@pytest.mark.parametrize(
    "change,code",
    [
        ({"tax": "1.00"}, "tax"),
        ({"total": "1000.01"}, "total"),
        ({"currency": "USD"}, "currency"),
        ({"supplier": "Wrong seller"}, "supplier"),
        ({"subtotal": "999.00"}, "subtotal"),
    ],
)
def test_critical_rules(env, change, code):
    _, samples = env
    sample = samples[1]
    payload = dict(sample["expected"], **change)
    assert code in {x["code"] for x in validate_invoice(payload, sample["order"])}


def test_numeric_evidence_does_not_match_substrings():
    rows = [{"text": "Total 1000.00", "page": 1, "box": [0, 0, 1, 1]}]
    assert "tax" not in extraction.locate_evidence({"tax": "0.00"}, rows)


def test_search_pagination_and_sql_input(env):
    import_sample(env)
    result = service.queue(env[0], "' OR 1=1 --", page=999)
    assert result["total"] == 0 and result["page"] == 1


def test_business_duplicate_blocks_second_file(env):
    engine, _ = env
    first = import_sample(env, 1)
    second = import_sample(env, 10)
    changed = service.mutate(engine, second["id"], second["version"], "edit", "reviewer", first["payload"])
    assert any(x["code"] == "duplicate_invoice" for x in changed["issues"])


def test_claim_is_exclusive(env):
    engine, samples = env
    s = samples[1]
    service.intake(engine, (db.ROOT / "fixtures" / s["file"]).read_bytes(), s["file"], "replay")
    with ThreadPoolExecutor(2) as pool:
        claims = list(pool.map(lambda x: db.claim(engine, str(x)), range(2)))
    assert sum(x is not None for x in claims) == 1


def test_second_invoice_cannot_allocate_approved_order(env):
    engine, _ = env
    first, second = import_sample(env, 1), import_sample(env, 10)
    payload = copy.deepcopy(first["payload"])
    payload["invoice_number"] = "SECOND-INVOICE"
    second = service.mutate(engine, second["id"], second["version"], "edit", "reviewer", payload)
    service.mutate(engine, first["id"], first["version"], "approve", "reviewer")
    with pytest.raises(service.Conflict):
        service.mutate(engine, second["id"], second["version"], "approve", "reviewer")


def test_synced_revision_is_immutable(env):
    engine, _ = env
    doc = import_sample(env)
    doc = service.mutate(engine, doc["id"], doc["version"], "approve", "reviewer")
    doc = service.mutate(engine, doc["id"], doc["version"], "sync", "reviewer")
    worker.run_job(engine, db.claim(engine, "test"))
    doc = service.get_document(engine, doc["id"])
    with pytest.raises(service.Conflict):
        service.mutate(engine, doc["id"], doc["version"], "edit", "reviewer", doc["payload"])
