"""Portable relational store and atomic, lease-based job claims."""

import os
import time
import uuid
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    select,
    update,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("MATCHBOOK_DATA", str(ROOT / "data")))
DATA.mkdir(parents=True, exist_ok=True)
metadata = MetaData()
documents = Table(
    "documents",
    metadata,
    Column("id", String(40), primary_key=True),
    Column("sha256", String(64), unique=True),
    Column("filename", String(200)),
    Column("path", Text),
    Column("status", String(30)),
    Column("version", Integer, default=1),
    Column("revision", Integer, default=0),
    Column("created", Float),
    Column("updated", Float),
    Column("mode", String(20)),
    Column("payload", JSON),
    Column("evidence", JSON),
    Column("issues", JSON),
    Column("pages", Integer),
    Column("text", Text),
    Column("approved_by", String(80)),
    Column("remote_id", String(100)),
    Column("error", Text),
    Column("elapsed", Float),
    Column("source_engine", String(50)),
)
revisions = Table(
    "revisions",
    metadata,
    Column("id", String(40), primary_key=True),
    Column("document_id", String(40), index=True),
    Column("revision", Integer),
    Column("payload", JSON),
    Column("actor", String(80)),
    Column("created", Float),
)
events = Table(
    "events",
    metadata,
    Column("id", String(40), primary_key=True),
    Column("document_id", String(40), index=True),
    Column("action", String(100)),
    Column("actor", String(80)),
    Column("detail", Text),
    Column("created", Float),
)
orders = Table(
    "orders",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("supplier", String(200)),
    Column("currency", String(3)),
    Column("items", JSON),
    Column("source", String(30)),
    Column("receipt_id", String(100)),
)
allocations = Table(
    "allocations",
    metadata,
    Column("order_id", String(100), primary_key=True),
    Column("document_id", String(40), unique=True),
)
jobs = Table(
    "jobs",
    metadata,
    Column("id", String(40), primary_key=True),
    Column("document_id", String(40), index=True),
    Column("kind", String(20)),
    Column("state", String(20)),
    Column("attempts", Integer, default=0),
    Column("available", Float),
    Column("lease_until", Float),
    Column("owner", String(40)),
    Column("error", Text),
    Column("created", Float),
)
syncs = Table(
    "syncs",
    metadata,
    Column("reference", String(100), primary_key=True),
    Column("document_id", String(40)),
    Column("revision", Integer),
    Column("state", String(30)),
    Column("remote_id", String(100)),
    Column("payload", JSON),
    Column("created", Float),
)
sandbox_drafts = Table(
    "sandbox_drafts",
    metadata,
    Column("reference", String(100), primary_key=True),
    Column("name", String(100), unique=True),
    Column("payload", JSON),
    Column("created", Float),
)
sessions = Table(
    "sessions",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("role", String(20)),
    Column("expires", Float),
)
heartbeats = Table("heartbeats", metadata, Column("id", String(40), primary_key=True), Column("seen", Float))


def uid():
    return uuid.uuid4().hex


def make_engine(url=None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///" + str(DATA / "matchbook.db"))
    engine = create_engine(
        url, connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")

    metadata.create_all(engine)
    return engine


def audit(conn, document_id, action, actor="worker", detail=""):
    conn.execute(
        events.insert().values(
            id=uid(), document_id=document_id, action=action, actor=actor, detail=detail, created=time.time()
        )
    )


def enqueue(conn, document_id, kind):
    conn.execute(
        jobs.insert().values(
            id=uid(),
            document_id=document_id,
            kind=kind,
            state="queued",
            attempts=0,
            available=time.time(),
            lease_until=0,
            created=time.time(),
        )
    )


def claim(engine, owner, lease=300):
    now = time.time()
    with engine.begin() as conn:
        row = (
            conn.execute(
                select(jobs)
                .where(jobs.c.state == "queued", jobs.c.available <= now)
                .order_by(jobs.c.created)
                .limit(1)
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        result = conn.execute(
            update(jobs)
            .where(jobs.c.id == row["id"], jobs.c.state == "queued")
            .values(state="running", owner=owner, lease_until=now + lease, attempts=jobs.c.attempts + 1)
        )
        return dict(row) | {"owner": owner, "attempts": row["attempts"] + 1} if result.rowcount == 1 else None


def recover(engine):
    with engine.begin() as conn:
        expired = (
            conn.execute(select(jobs).where(jobs.c.state == "running", jobs.c.lease_until < time.time()))
            .mappings()
            .all()
        )
        for job in expired:
            if job["kind"] == "sync":
                conn.execute(
                    update(documents)
                    .where(documents.c.id == job["document_id"])
                    .values(
                        status="sync_uncertain",
                        error="Worker interrupted. Reconcile the existing import reference before any further write.",
                        version=documents.c.version + 1,
                    )
                )
                conn.execute(update(jobs).where(jobs.c.id == job["id"]).values(state="uncertain", owner=None))
                audit(
                    conn,
                    job["document_id"],
                    "Sync needs reconciliation",
                    detail="Expired worker lease; no automatic re-dispatch.",
                )
            else:
                state = "queued" if job["attempts"] < 3 else "failed"
                conn.execute(
                    update(jobs)
                    .where(jobs.c.id == job["id"])
                    .values(state=state, owner=None, available=time.time())
                )
                conn.execute(
                    update(documents)
                    .where(documents.c.id == job["document_id"])
                    .values(
                        status="queued" if state == "queued" else "failed",
                        error="Extraction worker interrupted.",
                        version=documents.c.version + 1,
                    )
                )
