# Verification record

Verified locally on 5 September 2026. This is evidence for a personal portfolio build, not production certification.

## Completed

| Check | Actual result |
|---|---|
| Backend regression and contract suite | **31 passed**, including simultaneous approval/claims, duplicate input, revision invalidation, viewer restrictions, uncertain writes, source reconciliation and ERP HTTP contracts |
| Frontend | TypeScript check and Vite production build passed |
| UI static contract | Strict premium audit: **0 findings** |
| Design tokens | DESIGN.md lint: **0 errors**; 9 orphan-token warnings because runtime CSS owns the tokens. Project test checks every documented color against CSS |
| Real Chrome workflow | Login, search/no-results/clear, source highlighting, blocked approval, unsaved-edit dialog, draft confirmation/Escape, persisted sandbox draft, upload validation and narrow layout passed |
| Browser failure recovery | Failed request + Retry, session restoration without losing edits, mobile review passed |
| Automated accessibility | axe-core WCAG A/AA checks: **0 violations** on inbox, review and 390px mobile review. This is not a full accessibility certification |
| Live HTTP workflow | Two new PDFs uploaded through HTTP and processed by the actual local model/worker. Clean invoice approved and created a sandbox draft; price discrepancy blocked approval |
| OCR | Actual RapidOCR run on a rasterized invoice image recovered the invoice fields and table. Output saved; not a general scanned-document benchmark |
| Local model | Qwen3 0.6B Q8 GGUF loaded into Transformers/PyTorch float32 CPU; actual inference completed |
| Held-out evaluation | **24/24 completed**; see metrics below |

The test runner reports two upstream deprecation warnings from Starlette/httpx/AnyIO. They do not fail the suite. No claim of perfect cross-platform dependency compatibility is made.

## Held-out results

| Metric | Measured result |
|---|---|
| Raw model: entire invoice exactly correct | **14/24** |
| Hybrid pipeline: entire invoice exactly correct | **24/24** |
| Known discrepant invoices incorrectly passed by rules | **0** in this set |
| Extraction errors | **0/24** |
| End-to-end extraction latency p50 | **21.05 s** |
| End-to-end extraction latency p95 | **21.36 s** |

Numbers are compared with Decimal normalization; other fields and item ordering are exact. Pipeline correctness includes deterministic reconciliation with explicitly printed numeric values. It must not be described as the model itself achieving 24/24 accuracy.

The set consists of synthetic, digital, single-line invoices from two held-out supplier layouts. These layouts share the same simple table structure with development documents. This is a modest regression/generalization check, **not proof of performance on arbitrary supplier invoices**. No representative noisy-document, multilingual or handwritten benchmark was run. Peak memory and real operator time savings were not measured.

The initial ten-case development spike includes one model-startup connection failure and nine actual inference calls. Its report is retained as development history and is not the final benchmark. The final 24-case run started with the model available. Source files were formatted after that evaluation began; its start-of-run source hash is preserved, and the release environment snapshot records current file hashes.

## Evidence files

- [Browser workflow](evidence/browser-check.json)
- [Accessibility checks](evidence/accessibility.json)
- [Live HTTP-to-worker-to-model workflow](evidence/live-http-workflow.json)
- [Held-out records, model outputs, corrections and metrics](evidence/heldout-evaluation.json)
- [Development model spike](evidence/local-model-spike.json)
- [Actual OCR text](evidence/ocr-spike.txt)
- [Recorded walkthrough](Matchbook-walkthrough.webm)
- [Screenshots](screenshots/03-three-way-review.png)

## Explicitly incomplete or unverified

**Live ERPNext is not complete.** Windows lacks installed WSL/Docker; no ERPNext instance or user-provided service credentials were available. The adapter is implemented and mock-transport tested, with read-back validation, but still needs real master-data/accounting configuration and end-to-end verification. Current draft records belong to the labelled local sandbox.

**PostgreSQL has not been run.** The verified database is SQLite. SQLAlchemy accepts PostgreSQL configuration; this is not evidence of a PostgreSQL deployment. Alembic migrations, distributed deployment and background reference-data refresh remain future work.

**n8n has not executed the included workflow.** Installation was attempted but stopped after slow/failing package downloads. The JSON is an integration example, not proof of n8n execution. The Python HTTP batch client is separate and must not be represented as n8n.

The original proposed stack included Docling, Celery/Redis and a full ERPNext demo. The delivered Windows-first stack deliberately uses RapidOCR/PDFium, a leased SQL worker and an explicit sandbox. Neither README nor CV should list the proposed technologies as implemented experience.

Public hosting, enterprise auth, real customer documents, automatic payments and guaranteed hiring outcomes are outside this delivery.
