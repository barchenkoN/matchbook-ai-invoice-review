# Local runbook

## Start and stop

Run `start.ps1` or double-click `Start-Matchbook.cmd`. Core dependencies must already be installed through `setup.ps1`. The launcher seeds examples if absent, starts the API and worker, and starts the optional model only if its dependencies/data exist. It opens the browser unless `-NoBrowser` is specified. The frontend is prebuilt in `frontend/dist`.

Keep the launcher terminal open. Ctrl+C terminates only the processes this launch created. If a matching API is already running, the launcher opens it instead of duplicating services. Model initialization can take time; System health distinguishes a connected endpoint from an offline one.

## Common recovery

| Symptom | Action |
|---|---|
| Page unavailable | Start the launcher; check `runtime/app.err.log` and port 8787 |
| Jobs stay queued | Check worker status and `runtime/worker.err.log`; restart the launcher |
| Local model offline | Run `setup.ps1 -WithAI`, then restart; check model logs and free memory |
| Replay rejects a file | Use a bundled fixture PDF or select local AI; replay is not a generic parser |
| Extraction failed | Inspect the original, use a clearer supported document, and Retry extraction |
| Approval blocked | Resolve source/PO/receipt issues; do not falsify a supplier document to pass checks |
| Stale revision | Keep/copy your edits, refresh the invoice, compare changes and save a new revision |
| Sync on hold | Reconcile the existing reference; never create an additional draft by bypassing the state machine |
| No unique draft found | Keep it on hold and inspect the destination; automatic redispatch is intentionally unavailable |

Expired extraction leases recover on worker startup. Expired sync leases remain uncertain. Ordinary processing errors require explicit retry. Original files and revisions remain under `data/`; no automatic deletion or silent reset is performed.

## Fresh demo data without deleting existing work

Set `MATCHBOOK_DATA` to a new local directory before launch. This creates a separate database and document store. Existing data remains untouched. `DATABASE_URL` overrides the database location; do not accidentally reuse a personal database for browser tests.

## Optional ERPNext

Use a separately provisioned ERPNext instance. Set `ERP_MODE=erpnext`, `ERP_URL`, `ERP_COMPANY`, `ERP_API_KEY`, `ERP_API_SECRET`, and `ERP_REFERENCE_FIELD`. Create a dedicated least-privilege service user and a unique `custom_matchbook_reference` field. Configure suppliers, items, accounts and supported order/receipt records. Import reference snapshots using:

```powershell
./.venv/Scripts/python.exe -m tools.import_erp_order YOUR_PO YOUR_RECEIPT
```

Before presenting this as completed integration, execute and document draft creation/read-back, duplicate concurrent requests, response loss after commit, reconciliation, revoked permissions and changed receipt data. This checklist remains **unexecuted against live ERPNext** in the current delivery. Do not use the disposable Frappe demo deployment as production hosting.

## Reproducing evidence

Tests: `python -m pytest -q`. UI build: `pnpm --dir frontend run build`. Browser check: `python -m tools.browser_check` with installed Chrome and Playwright FFmpeg. Development feasibility: `python -m tools.spike`. Final synthetic evaluation: `python -m tools.evaluate` with the model ready and no other model jobs competing.

The evaluation is intentionally sequential on this CPU. Closing its terminal interrupts the run; the partial report states completed versus planned documents. A completed run must say 24 of 24. Never report planned samples as executed samples.
