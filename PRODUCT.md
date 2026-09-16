# Matchbook implementation contract

Personal portfolio project, synthetic data, no real customers or payments. Authoritative original brief: `../project-briefs/matchbook/PROJECT-BRIEF.uk.md`.

## Implementation decisions
Windows has no installed WSL/Docker. Deliver a native local application with a durable SQL worker, plus an ERPNext adapter and explicit sandbox integration. Real ERPNext remains unverified until a live instance is available. Never label the sandbox as ERPNext.

The default database is SQLite for frictionless Windows startup; SQLAlchemy also supports PostgreSQL through DATABASE_URL. PostgreSQL operation requires its own verification. A lease-based SQL job queue avoids a Windows-incompatible Celery deployment and Redis requirement. This is an intentional architecture change, not a claim of Celery experience.

Digital PDF parsing uses pdfplumber with source coordinates; scans use RapidOCR ONNX with page images. This replaces the heavier Docling stack for this machine. Local structured inference uses llama.cpp's OpenAI-compatible endpoint, with Ollama supported as another compatible endpoint. No paid API needed; recorded fixtures are explicitly replay only.

## Domain policy
One fictional company, EUR, ISO dates, 1–3 pages, max 20 lines, known SKU mappings. Invoice/PO/receipt currency and supplier must match. Decimal amounts, two-place HALF_UP rounding. Tax must be zero in v1; nonzero tax blocks as unsupported. Partial/repeated billing against the same receipt blocks; no tax/legal interpretation.

Unknown, unsupported, missing or contradictory critical facts block approval. Quantity cannot exceed receipt; unit price must exactly match PO; totals must reconcile. Model facts need source evidence, and manual changes are explicitly identified and audited.

Lifecycle: queued → processing → needs_review → approved → syncing → synced; separate failed and sync_uncertain. Approve only a valid current revision. Editing before sync returns to needs_review and invalidates approval. No editing during syncing, after synced or while uncertain. Approval and sync requests use optimistic version checks. File hash uniqueness is distinct from business invoice identity. No deletion endpoints.

The worker claims jobs with atomic SQL updates and expiring leases. Retried extraction is safe. A sync job that may have written externally is never blindly replayed; it enters reconciliation. Draft-only ERP writes record an external reference and verify read-back. Sandbox uses a unique reference transactionally. ERPNext does not inherit that guarantee without configured provider-side uniqueness.

## Permissions and data
Local viewer reads; reviewer uploads, edits, approves and queues sync. Default local demo sign-in explicitly marked demo, selectable roles for inspection, not enterprise identity. With MATCHBOOK_DEMO_AUTH=0, credentials are generated locally and demo sign-in disabled. Bind loopback. Cookies carry opaque random server-side sessions; no client role trust. Same-origin mutation protection. Files limited to PDF/PNG/JPEG, 10 MB, 3 pages, bounded rendered dimensions. Original documents and revisions retained locally; no public telemetry or remote document delivery except explicitly configured model/ERP endpoints.
