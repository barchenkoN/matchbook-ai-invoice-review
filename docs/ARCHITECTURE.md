# Architecture decisions

## ADR 001 — Windows-first runtime

The host has 16 GB RAM and no installed Docker/WSL. The standard ERPNext demo stack is therefore not runnable as-is. We ship native Python, a static React build, SQLite and a separate worker. SQLAlchemy accepts a PostgreSQL URL, but portability is not the same as a verified PostgreSQL deployment.

Application Control blocked the downloaded llama.cpp executable. No security policy was changed and that executable is not used. Transformers loads the data-only GGUF weights through the installed Python runtime, dequantizing them to float32 for CPU inference. This uses more memory than native quantized inference, but avoids a GPU requirement. The optional model service binds only to `127.0.0.1:8091`.

## ADR 002 — Separate extraction from validation

PDF/OCR supplies source text and normalized page boxes. A local model proposes an invoice structure. Pydantic validates the response. A conservative parser can replace numeric candidates only when explicit source labels or a uniquely matched SKU row supply the number. Both raw response and corrections remain in `data/documents/<id>/extraction.json`.

Decimal rules then check the actual extracted document, not an automatically balanced substitute. A printed wrong total stays wrong and blocks approval. Source locations are lexical evidence, not calibrated confidence. Semantic ambiguity still needs a human.

## ADR 003 — Approval owns a revision

Each document has an optimistic version and a content revision. Edits create a new revision and invalidate approval. Compare-and-swap rejects simultaneous writes. A unique order allocation prevents two different documents from concurrently approving against the same receipt under the deliberately restrictive one-invoice-per-order policy.

Invoices cannot be edited after sync starts or while its outcome is uncertain. No delete endpoint exists. Audit events are append-only through the application; this is not a cryptographically tamper-proof ledger against database administrators.

## ADR 004 — Leased SQL queue

The API inserts a job in the same transaction as the document state change. A separate worker claims it with a conditional update and a five-minute lease. Another worker cannot simultaneously claim the same job. Extraction can recover after lease expiry, up to three interrupted claims. Ordinary extraction errors remain failed for explicit operator retry; no claim of generic automatic exponential-backoff retry is made.

The worker checks ownership before committing its result. Model calls have a 180-second timeout; the HTTP model server permits one inference at a time. The worker is intended for bounded 1–3-page documents. Very slow OCR or a pathological parser can outlast a lease; a production deployment would add process isolation, per-stage hard timeouts and a heartbeat renewal protocol.

For an interrupted write, recovery is conservative: `sync_uncertain`. No blind second POST is sent. Reconciliation looks up the original import reference and verifies a unique matching draft. A missing result keeps the invoice on hold.

## ADR 005 — Integration claims are explicit

The verified sandbox is a local relational table with a unique import reference. It is not ERPNext. ERPNext mode sends authenticated REST requests, creates only `docstatus=0`, and verifies supplier, company, invoice number, currency, amount and item values on read-back. HTTP contract tests use a mock transport; they are not evidence of a live ERP run.

A real instance needs master data, accounting configuration, appropriate service-account permissions, a unique custom reference field and real PO/receipt snapshots. `tools/import_erp_order.py` reads reference records, but it too awaits live verification. Provider schema details and accounting defaults may require adaptation. Snapshot freshness is a remaining limitation: there is no automatic live refresh before approval in this version.

## ADR 006 — Local security boundary

Viewer/reviewer roles are enforced server-side using opaque random, expiring session cookies. Cookies are HttpOnly and SameSite strict. Mutations check origin, and the server accepts only loopback hostnames. Uploads check extension, magic bytes, size and document dimensions. There is no public deployment, account registration, enterprise SSO, rate-limit system or encrypted document storage claim.

Demo authentication deliberately lets an evaluator choose a role. Password mode disables that shortcut; credentials are supplied through process environment, never the frontend. The `.env.example` is documentation and is not automatically loaded.

## ADR 007 — Evaluation is a product artifact

Development examples informed the hybrid extraction rule. The final split reserves two supplier layouts and is evaluated separately. All templates still share a simple one-line table, so this is a limited synthetic benchmark. Raw-model exactness, pipeline exactness, errors and unsafe passes are reported separately with numeric Decimal normalization. More realistic multi-line, noisy, multilingual and genuinely independent supplier documents are needed before making broader accuracy claims.
