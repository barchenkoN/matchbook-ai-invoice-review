"""Explicit sandbox and ERPNext adapters. Unknown write outcomes never mean safe retry."""

import os
import time
from urllib.parse import quote

import httpx
from sqlalchemy import select

from app.db import sandbox_drafts, syncs


def mode():
    value = os.getenv("ERP_MODE", "sandbox")
    if value not in ("sandbox", "erpnext"):
        raise ValueError("ERP_MODE must be sandbox or erpnext.")
    return value


def create_draft(engine, reference, payload):
    if mode() == "sandbox":
        with engine.begin() as conn:
            existing = (
                conn.execute(select(sandbox_drafts).where(sandbox_drafts.c.reference == reference))
                .mappings()
                .first()
            )
            if existing:
                return existing["name"]
            name = "DEMO-PI-" + reference[-10:].upper()
            conn.execute(
                sandbox_drafts.insert().values(
                    reference=reference, name=name, payload=payload, created=time.time()
                )
            )
            return name
    body = {
        "doctype": "Purchase Invoice",
        "docstatus": 0,
        "company": os.environ["ERP_COMPANY"],
        "supplier": payload["supplier"],
        "bill_no": payload["invoice_number"],
        "bill_date": payload["invoice_date"],
        "posting_date": payload["invoice_date"],
        "currency": payload["currency"],
        "remarks": "Matchbook import " + reference,
        os.getenv("ERP_REFERENCE_FIELD", "custom_matchbook_reference"): reference,
        "items": [
            {
                "item_code": x["sku"],
                "qty": x["quantity"],
                "rate": x["unit_price"],
                "purchase_order": payload["po_number"],
            }
            for x in payload["items"]
        ],
    }
    with client() as api:
        response = api.post("/api/resource/Purchase Invoice", json=body)
        response.raise_for_status()
        name = response.json()["data"]["name"]
        remote = api.get("/api/resource/Purchase Invoice/" + quote(name, safe=""))
        remote.raise_for_status()
        data = remote.json()["data"]
        verify_remote(data, payload, reference)
        return name


def client():
    return httpx.Client(
        base_url=os.environ["ERP_URL"].rstrip("/"),
        timeout=25,
        headers={"Authorization": "token " + os.environ["ERP_API_KEY"] + ":" + os.environ["ERP_API_SECRET"]},
    )


def reconcile(engine, reference):
    if mode() == "sandbox":
        with engine.connect() as conn:
            return conn.execute(
                select(sandbox_drafts.c.name).where(sandbox_drafts.c.reference == reference)
            ).scalar()
    import json

    with client() as api:
        response = api.get(
            "/api/resource/Purchase Invoice",
            params={
                "filters": json.dumps(
                    [[os.getenv("ERP_REFERENCE_FIELD", "custom_matchbook_reference"), "=", reference]]
                ),
                "fields": json.dumps(["name", "docstatus"]),
                "limit_page_length": 2,
            },
        )
        response.raise_for_status()
        rows = response.json()["data"]
        if len(rows) != 1 or rows[0]["docstatus"] != 0:
            return None
        name = rows[0]["name"]
        remote = api.get("/api/resource/Purchase Invoice/" + quote(name, safe=""))
        remote.raise_for_status()
        with engine.connect() as conn:
            payload = conn.execute(select(syncs.c.payload).where(syncs.c.reference == reference)).scalar()
        if not payload:
            return None
        verify_remote(remote.json()["data"], payload, reference)
        return name


def verify_remote(data, payload, reference):
    from app.domain import money

    ref_field = os.getenv("ERP_REFERENCE_FIELD", "custom_matchbook_reference")
    checks = [
        data.get("docstatus") == 0,
        data.get(ref_field) == reference,
        data.get("supplier") == payload["supplier"],
        data.get("bill_no") == payload["invoice_number"],
        data.get("currency") == payload["currency"],
        data.get("company") == os.environ["ERP_COMPANY"],
        money(data.get("grand_total", -1)) == money(payload["total"]),
    ]
    remote_items = data.get("items", [])
    if len(remote_items) != len(payload["items"]):
        checks.append(False)
    else:
        from decimal import Decimal

        checks.extend(
            a.get("item_code") == b["sku"]
            and Decimal(str(a.get("qty", -1))) == Decimal(b["quantity"])
            and money(a.get("rate", -1)) == money(b["unit_price"])
            for a, b in zip(remote_items, payload["items"], strict=True)
        )
    if not all(checks):
        raise ValueError("ERP read-back differs from the approved draft. Keep the import on hold.")
