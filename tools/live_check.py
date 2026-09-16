"""Real HTTP upload -> worker -> local inference -> approval -> sandbox draft."""

import json
import time

import httpx

from app.db import ROOT

records = []
with httpx.Client(base_url="http://127.0.0.1:8787", timeout=30) as client:
    client.post("/api/login", json={"role": "reviewer"}).raise_for_status()
    for filename in ["INV-2026-1003.pdf", "INV-2026-1005.pdf"]:
        with (ROOT / "fixtures" / filename).open("rb") as file:
            result = client.post(
                "/api/invoices", data={"mode": "local"}, files={"file": (filename, file, "application/pdf")}
            )
        result.raise_for_status()
        doc_id = result.json()["id"]
        for _ in range(120):
            doc = client.get("/api/invoices/" + doc_id).json()
            if doc["status"] not in ("queued", "processing"):
                break
            time.sleep(1)
        assert doc["mode"] == "local", "This must be live inference, not a replayed duplicate."
        assert doc["status"] in ("needs_review", "synced"), doc
        if filename.endswith("1003.pdf") and doc["status"] != "synced":
            assert doc["issues"] == []
            approved = client.post(
                f"/api/invoices/{doc_id}/actions/approve", json={"version": doc["version"]}
            )
            approved.raise_for_status()
            queued = client.post(
                f"/api/invoices/{doc_id}/actions/sync", json={"version": approved.json()["version"]}
            )
            queued.raise_for_status()
            for _ in range(20):
                doc = client.get("/api/invoices/" + doc_id).json()
                if doc["status"] == "synced":
                    break
                time.sleep(1)
            assert doc["status"] == "synced"
        elif filename.endswith("1005.pdf"):
            assert "price" in {x["code"] for x in doc["issues"]}
            assert (
                client.post(
                    f"/api/invoices/{doc_id}/actions/approve", json={"version": doc["version"]}
                ).status_code
                == 409
            )
        records.append(doc)
        print(filename, doc["status"], doc["elapsed"], flush=True)
(ROOT / "docs/evidence/live-http-workflow.json").write_text(
    json.dumps({"destination": "local sandbox, not ERPNext", "records": records}, indent=2), encoding="utf-8"
)
