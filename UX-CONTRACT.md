# Matchbook interaction contract

Business authority: `PRODUCT.md`, based on the approved project brief. API state transitions and permissions are enforced server-side. This new project has no existing shared UI owners; Relay was inspected as a sibling and its labels for simulation must remain equally explicit here.

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | native select in Field | DESIGN.md | status, mode | browser keyboard |
| Date | typed ISO date Field | PRODUCT.md | invoice edit | validation tests |
| Form | Field / app submit handlers | PRODUCT.md | upload, review, sign-in | API and browser |
| Scrollbar | global styles.css baseline | DESIGN.md | horizontal table | computed style |
| Toast | Notice / live region | this contract | success, error | browser |
| CRUD | API / queue and detail controllers | PRODUCT.md | intake, revision, approval | full workflow |

No bulk selection, hard delete, payments or legal claims. Draft-only external write uses an explicit confirmation naming the target system. Secrets stay server-side; local session cookies are HttpOnly/SameSite strict. Public hosting is outside this delivery.

Queue: server pagination, 8 rows, URL stores status/page/invoice; search is transient to avoid putting supplier text in history. Search is 300ms debounced, IME-safe and stale-safe; clear is immediate. Loading, error with retry, empty and no-results are distinct. Sorting fixed newest-first and stated in UI.

Upload selects the created document and displays durable processing state. Editing stays on the same detail, invalidates approval and retains revisions. Duplicate submissions are blocked. Stale revisions are rejected with a refresh hint; input remains intact. Dirty forms use an app-owned navigation guard and beforeunload only for real unload.

All forms noValidate, named fields, inline persistent errors, first invalid field focus. One shared modal owns focus restoration, Escape and inert background. Pending writes keep the dialog open; failure remains visible there. Viewer cannot mutate. Authentication expiry gives a sign-in path without silently claiming a save.

English en-GB, UTC timestamps, ISO date-only input, EUR amounts. No dark-mode toggle. Natural page scrolling; horizontal table scrolling on narrow screens. Keyboard focus, reduced motion and forced colors supported. No certification claims.
