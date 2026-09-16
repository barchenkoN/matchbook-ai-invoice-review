import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  Layers,
  Search,
  Settings2,
  ShieldCheck,
  Upload,
  Workflow,
  X,
  Link2,
  RefreshCw,
  ScanLine,
  LogOut,
} from "lucide-react";
import {
  api,
  money,
  timestamp,
  type Invoice,
  type Payload,
  type Queue,
  type System,
  type User,
  type Order,
  type Evidence,
} from "./types";
import { Badge, Button, Field, Modal, Notice } from "./ui";
import "./styles.css";

function App() {
  const params = new URLSearchParams(location.search);
  const [user, setUser] = useState<User | null>(null),
    [authReady, setAuthReady] = useState(false),
    [demo, setDemo] = useState(true);
  const requestedView = params.get("view") ?? "invoices";
  const [view, setView] = useState(
      ["invoices", "orders", "drafts", "system"].includes(requestedView)
        ? requestedView
        : "invoices",
    ),
    [selected, setSelected] = useState(params.get("invoice") ?? "");
  const [status, setStatus] = useState(params.get("status") ?? ""),
    [page, setPage] = useState(
      Math.max(1, Math.min(100000, Number(params.get("page")) || 1)),
    );
  const [search, setSearch] = useState(""),
    [committed, setCommitted] = useState(""),
    [composing, setComposing] = useState(false);
  const [queue, setQueue] = useState<Queue | null>(null),
    [doc, setDoc] = useState<Invoice | null>(null),
    [system, setSystem] = useState<System | null>(null);
  const [loading, setLoading] = useState(false),
    [detailLoading, setDetailLoading] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [refresh, setRefresh] = useState(0);
  const [edit, setEdit] = useState<Payload | null>(null),
    [dirty, setDirty] = useState(false),
    [pendingNav, setPendingNav] = useState<(() => void) | null>(null);
  const [syncOpen, setSyncOpen] = useState(false),
    [actionError, setActionError] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const refreshAll = () => setRefresh((x) => x + 1);
  useEffect(() => {
    const expired = () => {
      if (user) setSessionExpired(true);
    };
    window.addEventListener("matchbook:session-expired", expired);
    return () =>
      window.removeEventListener("matchbook:session-expired", expired);
  }, [user]);
  useEffect(() => {
    api<User>("/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setAuthReady(true));
    api<{ demo: boolean }>("/auth")
      .then((x) => setDemo(x.demo))
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!composing && search !== committed) {
      const id = setTimeout(() => {
        setCommitted(search);
        setPage(1);
      }, 300);
      return () => clearTimeout(id);
    }
  }, [search, composing, committed]);
  useEffect(() => {
    const p = new URLSearchParams();
    if (view !== "invoices") p.set("view", view);
    if (selected) p.set("invoice", selected);
    if (status) p.set("status", status);
    if (page > 1) p.set("page", String(page));
    history.replaceState(
      null,
      "",
      `${location.pathname}${p.size ? "?" + p : ""}`,
    );
    document.title = `Matchbook · ${selected ? (doc?.payload?.invoice_number ?? "Invoice review") : view === "invoices" ? "Invoice inbox" : view === "orders" ? "Purchase orders" : view === "drafts" ? "Draft register" : "System health"}`;
  }, [view, selected, status, page, doc?.payload?.invoice_number]);
  useEffect(() => {
    if (!user) return;
    const ctrl = new AbortController();
    setLoading(true);
    setError("");
    api<Queue>(
      `/invoices?q=${encodeURIComponent(committed)}&status=${status}&page=${page}`,
      { signal: ctrl.signal },
    )
      .then((x) => {
        setQueue(x);
        if (x.page !== page) setPage(x.page);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [user, committed, status, page, refresh]);
  useEffect(() => {
    if (!user || !selected) {
      setDoc(null);
      return;
    }
    const ctrl = new AbortController();
    setDetailLoading(true);
    api<Invoice>("/invoices/" + selected, { signal: ctrl.signal })
      .then(setDoc)
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setDetailLoading(false);
      });
    return () => ctrl.abort();
  }, [selected, user, refresh]);
  useEffect(() => {
    if (!user) return;
    let alive = true;
    const load = () =>
      api<System>("/system")
        .then((x) => {
          if (alive) setSystem(x);
        })
        .catch(() => {});
    load();
    const t = setInterval(load, 12000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [user, refresh]);
  useEffect(() => {
    if (!user || edit) return;
    const active =
      queue?.items.some((x) =>
        ["queued", "processing", "syncing"].includes(x.status),
      ) ||
      (doc && ["queued", "processing", "syncing"].includes(doc.status));
    if (active) {
      const t = setTimeout(refreshAll, 2000);
      return () => clearTimeout(t);
    }
  }, [user, queue, doc, edit, refresh]);
  useEffect(() => {
    if (!dirty) return;
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);
  const navigate = (fn: () => void) => {
    if (dirty) setPendingNav(() => fn);
    else {
      setEdit(null);
      setActionError("");
      fn();
    }
  };
  const openInvoice = (id: string) =>
    navigate(() => {
      setDoc(null);
      setSelected(id);
      setView("invoices");
      setError("");
      window.scrollTo(0, 0);
    });
  const changeView = (v: string) =>
    navigate(() => {
      setView(v);
      setSelected("");
      setError("");
    });
  async function action(kind: string) {
    if (!doc || busy) return;
    setBusy(true);
    setActionError("");
    try {
      const result = await api<Invoice>(`/invoices/${doc.id}/actions/${kind}`, {
        method: "POST",
        body: JSON.stringify({
          version: doc.version,
          payload: kind === "edit" ? edit : undefined,
        }),
      });
      setDoc(result);
      setSyncOpen(false);
      setEdit(null);
      setDirty(false);
      setNotice(
        kind === "edit"
          ? "Verified revision saved. Previous approval cleared."
          : kind === "approve"
            ? "Invoice approved. Ready to create a draft."
            : kind === "sync"
              ? "Draft creation queued. You can leave this page."
              : "Extraction queued.",
      );
      refreshAll();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reconcile() {
    if (!doc) return;
    setBusy(true);
    setActionError("");
    try {
      setDoc(
        await api<Invoice>(`/invoices/${doc.id}/reconcile`, {
          method: "POST",
          body: JSON.stringify({ version: doc.version }),
        }),
      );
      setNotice("Existing draft found. No additional write made.");
      refreshAll();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!authReady)
    return (
      <div className="boot">
        <div className="brand-mark" />
        <p>Opening your review desk…</p>
      </div>
    );
  if (!user) return <Login demo={demo} onLogin={setUser} />;
  const counts = queue?.counts ?? {};
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            changeView("invoices");
          }}
        >
          <span className="brand-mark" />
          matchbook<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">
          <span className="workspace-icon">A</span>
          <div>
            Alder Works<small>Procurement workspace</small>
          </div>
        </div>
        <p className="nav-label">Workspace</p>
        <nav aria-label="Main navigation">
          {[
            { id: "invoices", label: "Invoice inbox", icon: FileText },
            { id: "orders", label: "Purchase orders", icon: Layers },
            { id: "drafts", label: "Draft register", icon: Workflow },
            { id: "system", label: "System health", icon: Settings2 },
          ].map((n) => (
            <button
              key={n.id}
              className={`nav-item ${view === n.id ? "active" : ""}`}
              aria-current={view === n.id ? "page" : undefined}
              onClick={() => changeView(n.id)}
            >
              <n.icon size={18} />
              <span>{n.label}</span>
              {n.id === "invoices" && counts.needs_review ? (
                <b>{counts.needs_review}</b>
              ) : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sandbox-note">
            <ShieldCheck size={20} />
            <strong>Safe to explore</strong>
            <p>
              Synthetic documents.
              <br />
              Drafts only. No payments.
            </p>
          </div>
          <div className="profile">
            <span className="avatar">
              {user.role === "reviewer" ? "NR" : "V"}
            </span>
            <div>
              {user.demo
                ? user.role === "reviewer"
                  ? "Demo reviewer"
                  : "Demo viewer"
                : user.role}
              <small>
                {user.demo
                  ? "Local demo session"
                  : "Local authenticated session"}
              </small>
            </div>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={() =>
                navigate(() => {
                  api("/logout", { method: "POST" }).then(() => setUser(null));
                })
              }
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace</span>
            <ChevronRight size={14} />
            <span>
              {selected
                ? "Invoice review"
                : view === "invoices"
                  ? "Invoice inbox"
                  : view === "orders"
                    ? "Purchase orders"
                    : view === "drafts"
                      ? "Draft register"
                      : "System health"}
            </span>
          </div>
          <div className="environment">
            <span className={`dot ${system?.worker_online ? "online" : ""}`} />
            {!system
              ? "Checking services…"
              : system.worker_online
                ? "Worker connected"
                : "Worker not connected"}
            <span className="divider" />
            <span>
              {system?.erp_mode === "erpnext"
                ? "ERPNext configured"
                : "Sandbox destination"}
            </span>
          </div>
        </header>
        <main id="main">
          <div className="notice-slot">
            <Notice message={notice} />
          </div>
          {error && (
            <div className="error-bar">
              <Notice message={error} error />
              <Button onClick={refreshAll}>Retry</Button>
            </div>
          )}
          {view === "invoices" && !selected && (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">Accounts payable</p>
                  <h1>Every invoice. Accounted for.</h1>
                  <p>
                    Match the document to the order. Resolve what doesn’t add
                    up.
                  </p>
                </div>
                <Button
                  variant="primary"
                  onClick={() => setUploadOpen(true)}
                  disabled={user.role !== "reviewer"}
                >
                  <Upload size={16} />
                  Upload invoice
                </Button>
              </div>
              <div className="metrics">
                <Metric
                  label="Awaiting review"
                  value={counts.needs_review ?? 0}
                  note="Ready for a human check"
                  accent="amber"
                />
                <Metric
                  label="Approved"
                  value={counts.approved ?? 0}
                  note="Cleared for draft creation"
                />
                <Metric
                  label="Drafts created"
                  value={counts.synced ?? 0}
                  note={
                    system?.erp_mode === "erpnext"
                      ? "ERPNext destination"
                      : "In the local sandbox"
                  }
                />
                <Metric
                  label="In progress"
                  value={
                    (counts.queued ?? 0) +
                    (counts.processing ?? 0) +
                    (counts.syncing ?? 0)
                  }
                  note="Processed by the background worker"
                />
              </div>
              <div className="panel inbox">
                <div className="panel-heading">
                  <div>
                    <h2>
                      Invoice inbox{" "}
                      <span className="count">{queue?.total ?? 0}</span>
                    </h2>
                    <p>Newest first · all amounts in EUR</p>
                  </div>
                  <Button
                    onClick={refreshAll}
                    aria-label="Refresh invoice inbox"
                  >
                    <RefreshCw size={16} />
                  </Button>
                </div>
                <div className="toolbar">
                  <div className="filter-buttons" aria-label="Invoice status">
                    {[
                      ["", "All invoices"],
                      ["needs_review", "Needs review"],
                      ["approved", "Approved"],
                      ["synced", "Draft created"],
                    ].map(([v, l]) => (
                      <button
                        key={v}
                        className={status === v ? "selected" : ""}
                        aria-pressed={status === v}
                        onClick={() => {
                          setStatus(v);
                          setPage(1);
                        }}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                  <div className="search">
                    <Search size={16} />
                    <input
                      aria-label="Search invoices"
                      ref={searchRef}
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      onCompositionStart={() => setComposing(true)}
                      onCompositionEnd={() => setComposing(false)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                          setCommitted(search);
                          setPage(1);
                        }
                      }}
                      placeholder="Search supplier or invoice…"
                    />
                    {search && (
                      <button
                        aria-label="Clear search"
                        onClick={() => {
                          setSearch("");
                          setCommitted("");
                          setPage(1);
                          searchRef.current?.focus();
                        }}
                      >
                        <X size={15} />
                      </button>
                    )}
                  </div>
                </div>
                <div className="table-frame" aria-busy={loading}>
                  <div className="loading-line" role="status">
                    {loading ? "Updating invoices…" : ""}
                  </div>
                  <div className="table-scroll">
                    <table>
                      <caption className="sr-only">
                        Supplier invoice review queue
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">Invoice / supplier</th>
                          <th scope="col">Purchase order</th>
                          <th scope="col">Amount</th>
                          <th scope="col">Review status</th>
                          <th scope="col">Extraction</th>
                          <th scope="col">
                            <span className="sr-only">Open</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {queue?.items.map((item) => (
                          <tr key={item.id}>
                            <td>
                              <a
                                className="invoice-link"
                                href={"?invoice=" + item.id}
                                onClick={(e) => {
                                  e.preventDefault();
                                  openInvoice(item.id);
                                }}
                              >
                                <span className="file-icon">
                                  <FileText size={19} />
                                </span>
                                <span>
                                  <strong>
                                    {item.payload?.supplier ?? item.filename}
                                  </strong>
                                  <small>
                                    {item.payload?.invoice_number ??
                                      "Reading document…"}
                                  </small>
                                </span>
                              </a>
                            </td>
                            <td className="mono">
                              {item.payload?.po_number ?? "—"}
                            </td>
                            <td className="amount">
                              {item.payload ? money(item.payload.total) : "—"}
                            </td>
                            <td>
                              <Badge status={item.status} />
                              {item.issues?.length > 0 && (
                                <small className="issue-count">
                                  {item.issues.length} blocking{" "}
                                  {item.issues.length === 1
                                    ? "check"
                                    : "checks"}
                                </small>
                              )}
                            </td>
                            <td>
                              <span className="mode-label">
                                {item.mode === "replay"
                                  ? "Recorded example"
                                  : "Local AI"}
                              </span>
                            </td>
                            <td>
                              <button
                                className="icon-button"
                                aria-label={
                                  "Review " +
                                  (item.payload?.invoice_number ??
                                    item.filename)
                                }
                                onClick={() => openInvoice(item.id)}
                              >
                                <ArrowRight size={17} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!loading && queue?.total === 0 && (
                    <div className="empty">
                      <Search size={30} />
                      <h3>
                        {search || status
                          ? "No matching invoices"
                          : "Your inbox is ready"}
                      </h3>
                      <p>
                        {search || status
                          ? "Try a different search or clear your filters."
                          : "Upload a supplier invoice to start a three-way check."}
                      </p>
                      <Button
                        onClick={() => {
                          setSearch("");
                          setCommitted("");
                          setStatus("");
                          setPage(1);
                        }}
                      >
                        Clear filters
                      </Button>
                    </div>
                  )}
                </div>
                <div className="pagination">
                  <span>
                    {queue?.total
                      ? `${(queue.page - 1) * 8 + 1}–${Math.min(queue.page * 8, queue.total)} of ${queue.total} invoices`
                      : "0 invoices"}
                  </span>
                  <nav aria-label="Invoice pages">
                    <Button
                      aria-label="Previous page"
                      disabled={page <= 1 || loading}
                      onClick={() => setPage((x) => x - 1)}
                    >
                      <ChevronLeft size={16} />
                    </Button>
                    <span>Page {page}</span>
                    <Button
                      aria-label="Next page"
                      disabled={!queue || page * 8 >= queue.total || loading}
                      onClick={() => setPage((x) => x + 1)}
                    >
                      <ChevronRight size={16} />
                    </Button>
                  </nav>
                </div>
              </div>
              <div className="workflow-note">
                <Link2 size={18} />
                <span>
                  <strong>A complete paper trail.</strong> Original document →
                  extracted fields → three-way check → human approval → draft.
                </span>
                <span className="subtle">No silent edits.</span>
              </div>
            </>
          )}
          {view === "invoices" &&
            selected &&
            (detailLoading && !doc ? (
              <div className="empty" role="status">
                Opening invoice…
              </div>
            ) : doc ? (
              <>
                <Button
                  variant="ghost"
                  onClick={() =>
                    navigate(() => {
                      setSelected("");
                      setDoc(null);
                    })
                  }
                >
                  <ArrowLeft size={16} />
                  Back to inbox
                </Button>
                <Review
                  doc={doc}
                  user={user}
                  system={system}
                  busy={busy}
                  edit={edit}
                  setEdit={(p) => {
                    setEdit(p);
                    setDirty(true);
                  }}
                  actionError={actionError}
                  onEdit={() => {
                    setEdit(structuredClone(doc.payload));
                    setActionError("");
                  }}
                  onCancel={() =>
                    navigate(() => {
                      setEdit(null);
                      setDirty(false);
                    })
                  }
                  onSave={() => action("edit")}
                  onApprove={() => action("approve")}
                  onSync={() => {
                    setActionError("");
                    setSyncOpen(true);
                  }}
                  onRetry={() => action("retry")}
                  onReconcile={reconcile}
                />
              </>
            ) : !error ? (
              <div className="empty">
                Invoice unavailable. Return to the inbox.
              </div>
            ) : null)}
          {view === "orders" && <Orders />}
          {view === "drafts" && <Drafts />}
          {view === "system" && (
            <SystemPage system={system} onRefresh={refreshAll} />
          )}
        </main>
        <footer className="app-footer">
          <span>Matchbook / supplier invoice operations</span>
          <span>Portfolio edition · synthetic data · v0.1</span>
        </footer>
      </div>
      {uploadOpen && (
        <UploadDialog
          onClose={() => setUploadOpen(false)}
          live={Boolean(system?.llm_online)}
          onUploaded={(id) => {
            setUploadOpen(false);
            openInvoice(id);
            refreshAll();
            setNotice(
              "Document received. Processing continues in the background.",
            );
          }}
        />
      )}
      {sessionExpired && (
        <RenewSession
          user={user}
          onClose={() => setSessionExpired(false)}
          onRenewed={() => {
            setSessionExpired(false);
            setActionError("");
            refreshAll();
            setNotice(
              "Session restored. Your unsaved edits are still available.",
            );
          }}
        />
      )}
      {syncOpen && doc && !sessionExpired && (
        <Modal
          title="Create a draft invoice?"
          onClose={() => setSyncOpen(false)}
          busy={busy}
        >
          <p>
            Create a draft for <strong>{doc.payload?.invoice_number}</strong>{" "}
            worth <strong>{money(doc.payload?.total)}</strong> in{" "}
            <strong>
              {system?.erp_mode === "erpnext" ? "ERPNext" : "the local sandbox"}
            </strong>
            .
          </p>
          <p>
            This does not post the invoice or make a payment. The approved
            revision will be locked.
          </p>
          {actionError && <Notice message={actionError} error />}
          <div className="dialog-actions">
            <Button
              autoFocus
              onClick={() => setSyncOpen(false)}
              disabled={busy}
            >
              Keep reviewing
            </Button>
            <Button
              variant="primary"
              busy={busy}
              onClick={() => action("sync")}
            >
              Create draft
            </Button>
          </div>
        </Modal>
      )}
      {pendingNav && (
        <Modal
          title="Discard unsaved changes?"
          onClose={() => setPendingNav(null)}
        >
          <p>
            Your changes have not been saved. Keep editing to preserve them.
          </p>
          <div className="dialog-actions">
            <Button autoFocus onClick={() => setPendingNav(null)}>
              Keep editing
            </Button>
            <Button
              variant="warning"
              onClick={() => {
                setDirty(false);
                setEdit(null);
                pendingNav();
                setPendingNav(null);
              }}
            >
              Discard changes
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function RenewSession({
  user,
  onClose,
  onRenewed,
}: {
  user: User;
  onClose: () => void;
  onRenewed: () => void;
}) {
  const [password, setPassword] = useState(""),
    [show, setShow] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <Modal title="Restore your session" onClose={onClose} busy={busy}>
      <p>
        Your session ended. Unsaved edits remain on this page. Sign in again
        before saving.
      </p>
      <form
        noValidate
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await api("/login", {
              method: "POST",
              body: JSON.stringify({ role: user.role, password }),
            });
            onRenewed();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {!user.demo && (
          <>
            <Field
              id="renew-password"
              label="Password"
              type={show ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button onClick={() => setShow(!show)} aria-pressed={show}>
              {show ? "Hide password" : "Show password"}
            </Button>
          </>
        )}
        <Notice message={error} error={Boolean(error)} />
        <div className="dialog-actions">
          <Button onClick={onClose} disabled={busy}>
            Keep page open
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            Restore session
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function Metric({
  label,
  value,
  note,
  accent = "",
}: {
  label: string;
  value: number;
  note: string;
  accent?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={accent}>{value.toString().padStart(2, "0")}</strong>
      <small>{note}</small>
    </div>
  );
}

function Login({
  demo,
  onLogin,
}: {
  demo: boolean;
  onLogin: (u: User) => void;
}) {
  const [role, setRole] = useState("reviewer"),
    [password, setPassword] = useState(""),
    [show, setShow] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <main className="login-page">
      <div className="login-story">
        <div className="brand">
          <span className="brand-mark" />
          matchbook.
        </div>
        <div>
          <p className="eyebrow">From document to decision</p>
          <h1>
            Make the numbers
            <br />
            tell the same story.
          </h1>
          <p>
            A review desk for supplier invoices.
            <br />
            Every discrepancy visible. Every decision traceable.
          </p>
          <div className="login-steps">
            <span>Purchase order</span>
            <Link2 />
            <span>Goods receipt</span>
            <Link2 />
            <span>Invoice</span>
          </div>
        </div>
        <p className="subtle">Built for a careful human in the loop.</p>
      </div>
      <div className="login-card">
        <span className="file-icon large">
          <ScanLine size={30} />
        </span>
        <h2>Open your workspace</h2>
        <p>
          {demo
            ? "Explore with synthetic documents and a local draft sandbox. No account or API key required."
            : "Sign in with your locally configured credentials."}
        </p>
        <form
          noValidate
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const u = await api<{ role: string }>("/login", {
                method: "POST",
                body: JSON.stringify({ role, password }),
              });
              onLogin({ ...u, demo });
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field" htmlFor="role">
            <span>Access level</span>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              <option value="reviewer">
                Reviewer — review and create drafts
              </option>
              <option value="viewer">Viewer — read-only access</option>
            </select>
          </label>
          {!demo && (
            <>
              <Field
                id="password"
                label="Password"
                type={show ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Button onClick={() => setShow(!show)} aria-pressed={show}>
                {show ? "Hide" : "Show"} password
              </Button>
            </>
          )}
          <Notice message={error} error={Boolean(error)} />
          <Button type="submit" variant="primary" busy={busy}>
            Enter workspace <ArrowRight size={16} />
          </Button>
        </form>
        <small>
          <ShieldCheck size={14} />{" "}
          {demo
            ? "Demo roles are for inspection, not enterprise identity."
            : "Credentials remain on this local machine."}
        </small>
      </div>
    </main>
  );
}

function Review({
  doc,
  user,
  system,
  busy,
  edit,
  setEdit,
  actionError,
  onEdit,
  onCancel,
  onSave,
  onApprove,
  onSync,
  onRetry,
  onReconcile,
}: {
  doc: Invoice;
  user: User;
  system: System | null;
  busy: boolean;
  edit: Payload | null;
  setEdit: (p: Payload) => void;
  actionError: string;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  onApprove: () => void;
  onSync: () => void;
  onRetry: () => void;
  onReconcile: () => void;
}) {
  const [evidence, setEvidence] = useState<Evidence | null>(null),
    [page, setPage] = useState(1),
    [tab, setTab] = useState("comparison"),
    [previewFailed, setPreviewFailed] = useState(false);
  useEffect(() => {
    setEvidence(null);
    setPage(1);
    setTab("comparison");
    setPreviewFailed(false);
  }, [doc.id]);
  const p = doc.payload,
    canWrite = user.role === "reviewer";
  const showEvidence = (key: string) => {
    const item = doc.evidence?.[key];
    if (item) {
      setEvidence(item);
      setPage(item.page);
      setPreviewFailed(false);
    }
  };
  const progress = ["queued", "processing"].includes(doc.status);
  return (
    <>
      <div className="review-heading">
        <div>
          <p className="eyebrow">
            Invoice review{" "}
            <span className="mono">/ {p?.invoice_number ?? doc.filename}</span>
          </p>
          <h1>{p?.supplier ?? "Reading your document"}</h1>
          <p>
            {p
              ? `${p.invoice_number} · ${p.invoice_date} · ${p.currency}`
              : doc.filename}
          </p>
        </div>
        <div>
          <Badge status={doc.status} />
          <strong className="review-total">{p ? money(p.total) : "—"}</strong>
        </div>
      </div>
      <div
        className="process-strip"
        role="region"
        aria-label="Invoice processing stages"
        tabIndex={0}
      >
        {[
          ["Received", true],
          ["Extracted", Boolean(p)],
          ["Validated", Boolean(p)],
          ["Approved", ["approved", "syncing", "synced"].includes(doc.status)],
          ["Draft created", doc.status === "synced"],
        ].map(([label, done], i) => (
          <div key={String(label)} className={done ? "complete" : ""}>
            <span>{done ? <Check size={13} /> : i + 1}</span>
            {label}
          </div>
        ))}
      </div>
      {doc.error && <Notice message={doc.error} error />}
      {progress && (
        <div className="processing-banner" role="status">
          <ScanLine size={20} />
          <div>
            <strong>
              {doc.status === "queued"
                ? "Waiting for the document worker"
                : "Reading and checking your document"}
            </strong>
            <p>
              You can return to the inbox. Processing continues independently.
            </p>
          </div>
        </div>
      )}
      <div className="review-grid">
        <section className="panel source-panel">
          <div className="panel-heading">
            <div>
              <h2>
                <FileText size={17} />
                Original document
              </h2>
              <p>{doc.filename}</p>
            </div>
            <a
              className="button outline"
              href={`/api/invoices/${doc.id}/original`}
            >
              <ArrowDownToLine size={16} />
              <span className="sr-only">Download original</span>
            </a>
          </div>
          <div className="document-stage">
            {doc.pages > 0 && !previewFailed ? (
              <div className="paper">
                <img
                  src={`/api/invoices/${doc.id}/pages/${page}`}
                  alt={`Original supplier invoice, page ${page}`}
                  onError={() => setPreviewFailed(true)}
                />
                {evidence?.box && evidence.page === page && (
                  <div
                    className="evidence-highlight"
                    style={{
                      left: evidence.box[0] * 100 + "%",
                      top: evidence.box[1] * 100 + "%",
                      width: (evidence.box[2] - evidence.box[0]) * 100 + "%",
                      height:
                        Math.max((evidence.box[3] - evidence.box[1]) * 100, 2) +
                        "%",
                    }}
                  />
                )}
              </div>
            ) : (
              <div className="empty">
                <FileText size={35} />
                <p>
                  {previewFailed
                    ? "Preview unavailable. Download the original document."
                    : "Preview appears after document processing."}
                </p>
              </div>
            )}
          </div>
          <div className="source-footer">
            <span>
              Page {page} of {doc.pages || "—"}
            </span>
            <div>
              <Button
                disabled={page <= 1}
                aria-label="Previous document page"
                onClick={() => {
                  setPage((x) => x - 1);
                  setPreviewFailed(false);
                }}
              >
                <ChevronLeft size={14} />
              </Button>
              <Button
                disabled={page >= doc.pages}
                aria-label="Next document page"
                onClick={() => {
                  setPage((x) => x + 1);
                  setPreviewFailed(false);
                }}
              >
                <ChevronRight size={14} />
              </Button>
            </div>
          </div>
          {evidence && (
            <div className="source-quote">
              <ScanLine size={15} />
              <div>
                <strong>
                  {evidence.manual
                    ? "Reviewer verification"
                    : "Located source text"}
                </strong>
                <p>{evidence.text}</p>
              </div>
            </div>
          )}
        </section>
        <section className="review-work">
          <div className="detail-tabs" aria-label="Review sections">
            {[
              ["comparison", "Three-way match"],
              ["fields", "Extracted fields"],
              ["history", "Activity & revisions"],
            ].map(([v, l]) => (
              <button
                key={v}
                aria-pressed={tab === v}
                className={tab === v ? "selected" : ""}
                onClick={() => setTab(v)}
              >
                {l}
              </button>
            ))}
          </div>
          {edit ? (
            <InvoiceEditor
              value={edit}
              onChange={setEdit}
              onSave={onSave}
              onCancel={onCancel}
              busy={busy}
              error={actionError}
            />
          ) : (
            <>
              {tab === "comparison" && (
                <>
                  <div
                    className={`match-summary ${doc.issues.length ? "has-issues" : "is-matched"}`}
                  >
                    <span className="summary-icon">
                      {doc.issues.length ? "!" : <Check size={22} />}
                    </span>
                    <div>
                      <h2>
                        {!p
                          ? "Check pending"
                          : doc.issues.length
                            ? `${doc.issues.length} ${doc.issues.length === 1 ? "discrepancy needs" : "discrepancies need"} a closer look`
                            : "The numbers line up"}
                      </h2>
                      <p>
                        {!p
                          ? "Waiting for extracted invoice data."
                          : doc.issues.length
                            ? "Resolve the differences before approving this invoice."
                            : "The invoice matches the purchase order and goods receipt."}
                      </p>
                    </div>
                  </div>
                  {doc.issues.map((issue, i) => (
                    <div className="issue-card" key={i}>
                      <div>
                        <strong>{issue.title}</strong>
                        <p>{issue.detail}</p>
                      </div>
                      <button
                        className="icon-button"
                        aria-label={"Show source for " + issue.title}
                        disabled={
                          !doc.evidence?.[
                            issue.line === null
                              ? issue.field
                              : `items.${issue.line}.${issue.code === "price" ? "unit_price" : "quantity"}`
                          ]
                        }
                        onClick={() =>
                          showEvidence(
                            issue.line === null
                              ? issue.field
                              : `items.${issue.line}.${issue.code === "price" ? "unit_price" : "quantity"}`,
                          )
                        }
                      >
                        <ScanLine size={18} />
                      </button>
                    </div>
                  ))}
                  {p && (
                    <div className="panel comparison-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Order · receipt · invoice</h2>
                          <p>
                            {doc.order?.id ?? "Order unavailable"} /{" "}
                            {doc.order?.receipt_id ?? "No goods receipt"}
                          </p>
                        </div>
                        <Link2 size={17} />
                      </div>
                      {p.items.map((line, i) => {
                        const order = doc.order?.items.find(
                          (x) => x.sku === line.sku,
                        );
                        return (
                          <div className="match-item" key={i}>
                            <div className="item-heading">
                              <strong>{line.description}</strong>
                              <span className="mono">{line.sku}</span>
                            </div>
                            <div className="match-columns">
                              <div>
                                <span>Ordered</span>
                                <strong>
                                  {order?.ordered ?? "—"} <small>units</small>
                                </strong>
                                <p>
                                  {order ? money(order.unit_price) : "—"} / unit
                                </p>
                              </div>
                              <div>
                                <span>Received</span>
                                <strong>
                                  {order?.received ?? "—"} <small>units</small>
                                </strong>
                                <p>Goods receipt</p>
                              </div>
                              <div
                                className={
                                  order &&
                                  (Number(line.quantity) >
                                    Number(order.received) ||
                                    Number(line.unit_price) !==
                                      Number(order.unit_price))
                                    ? "flagged"
                                    : ""
                                }
                              >
                                <span>Invoiced</span>
                                <button
                                  className="value-button"
                                  onClick={() =>
                                    showEvidence(`items.${i}.quantity`)
                                  }
                                >
                                  {line.quantity} <small>units</small>
                                  <ScanLine size={13} />
                                </button>
                                <button
                                  className="source-value"
                                  onClick={() =>
                                    showEvidence(`items.${i}.unit_price`)
                                  }
                                >
                                  {money(line.unit_price)} / unit
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                      <div className="total-row">
                        <span>Invoice total</span>
                        <strong>{money(p.total)}</strong>
                      </div>
                    </div>
                  )}
                  <div className="provenance">
                    <ShieldCheck size={17} />
                    <p>
                      {doc.mode === "replay"
                        ? "Recorded example: reference fields are loaded from the synthetic fixture."
                        : "Local AI extraction: model output is checked against document evidence and deterministic rules."}{" "}
                      {doc.elapsed !== null
                        ? `Document processing: ${doc.elapsed.toFixed(1)}s.`
                        : ""}
                    </p>
                  </div>
                </>
              )}
              {tab === "fields" && (
                <div className="panel field-readout">
                  <div className="panel-heading">
                    <h2>Extracted values</h2>
                    <span>Revision {doc.revision}</span>
                  </div>
                  {p &&
                    Object.entries(p)
                      .filter(([k]) => k !== "items")
                      .map(([key, value]) => (
                        <div className="readout" key={key}>
                          <span>{key.replaceAll("_", " ")}</span>
                          <button
                            onClick={() => showEvidence(key)}
                            className="source-value"
                            disabled={!doc.evidence?.[key]}
                          >
                            {String(value)}
                            <ScanLine size={14} />
                          </button>
                        </div>
                      ))}
                  <p className="help">
                    Select a value to locate its source. Reviewer-verified
                    values are labelled separately.
                  </p>
                </div>
              )}
              {tab === "history" && (
                <div className="panel history">
                  <div className="panel-heading">
                    <h2>Decision trail</h2>
                    <a
                      className="button ghost"
                      href={`/api/invoices/${doc.id}/export`}
                    >
                      <ArrowDownToLine size={15} />
                      Export
                    </a>
                  </div>
                  <ol>
                    {doc.events.map((event) => (
                      <li key={event.id}>
                        <span className="timeline-dot" />
                        <strong>{event.action}</strong>
                        <p>{event.detail}</p>
                        <small>
                          {event.actor} · {timestamp(event.created)}
                        </small>
                      </li>
                    ))}
                  </ol>
                  <details>
                    <summary>Saved revisions ({doc.revisions.length})</summary>
                    {doc.revisions.map((r) => (
                      <div className="revision" key={r.id}>
                        <strong>
                          Revision {r.revision} · {r.actor}
                        </strong>
                        <small>{timestamp(r.created)}</small>
                        <pre>{JSON.stringify(r.payload, null, 2)}</pre>
                      </div>
                    ))}
                  </details>
                </div>
              )}
              {actionError && <Notice message={actionError} error />}
              <div className="review-actions">
                {canWrite &&
                  p &&
                  ["needs_review", "approved"].includes(doc.status) && (
                    <Button onClick={onEdit}>Review & correct fields</Button>
                  )}
                {canWrite && doc.status === "needs_review" && (
                  <Button
                    variant="primary"
                    disabled={doc.issues.length > 0}
                    busy={busy}
                    onClick={onApprove}
                  >
                    <Check size={16} />
                    Approve invoice
                  </Button>
                )}
                {canWrite && doc.status === "approved" && (
                  <Button variant="primary" busy={busy} onClick={onSync}>
                    <Workflow size={16} />
                    Create draft
                  </Button>
                )}
                {canWrite && doc.status === "failed" && (
                  <Button variant="primary" busy={busy} onClick={onRetry}>
                    Retry extraction
                  </Button>
                )}
                {canWrite && doc.status === "sync_uncertain" && (
                  <Button variant="primary" busy={busy} onClick={onReconcile}>
                    Reconcile existing draft
                  </Button>
                )}
              </div>
              {doc.status === "synced" && (
                <div className="synced-card">
                  <Check size={20} />
                  <div>
                    <strong>{doc.remote_id}</strong>
                    <p>
                      Draft created in{" "}
                      {system?.erp_mode === "erpnext"
                        ? "ERPNext"
                        : "the local sandbox"}
                      . No payment made.
                    </p>
                  </div>
                </div>
              )}
              {!canWrite && (
                <p className="help">
                  Viewer access. A reviewer is required to change this invoice.
                </p>
              )}
              {doc.issues.length > 0 && doc.status === "needs_review" && (
                <p className="help">
                  Approval is unavailable while blocking discrepancies remain.
                </p>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}

function InvoiceEditor({
  value,
  onChange,
  onSave,
  onCancel,
  busy,
  error,
}: {
  value: Payload;
  onChange: (p: Payload) => void;
  onSave: () => void;
  onCancel: () => void;
  busy: boolean;
  error: string;
}) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const change = (key: string, val: string) =>
    onChange({ ...value, [key]: val });
  function save(e: React.FormEvent) {
    e.preventDefault();
    const bad: Record<string, string> = {};
    for (const [key, val] of Object.entries(value)) {
      if (key !== "items" && !String(val).trim()) bad[key] = "Enter a value.";
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value.invoice_date))
      bad.invoice_date = "Use YYYY-MM-DD.";
    for (const key of ["subtotal", "tax", "total"] as const)
      if (!/^\d+(\.\d{1,2})?$/.test(value[key]))
        bad[key] = "Use a positive decimal, such as 1000.00.";
    value.items.forEach((line, i) => {
      for (const key of ["quantity", "unit_price", "line_total"] as const)
        if (!/^\d+(\.\d{1,3})?$/.test(line[key]))
          bad[`line-${i}-${key}`] = "Enter a valid decimal.";
    });
    setErrors(bad);
    if (Object.keys(bad).length) {
      requestAnimationFrame(() =>
        document.getElementById(Object.keys(bad)[0])?.focus(),
      );
      return;
    }
    onSave();
  }
  return (
    <form className="panel editor" noValidate onSubmit={save}>
      <div className="panel-heading">
        <h2>Verify extracted fields</h2>
      </div>
      <p className="help">
        Check values against the source document. Saving confirms your review
        and clears any earlier approval. Never change a supplier’s bill merely
        to make the checks pass.
      </p>
      <div className="edit-grid">
        {(
          [
            "supplier",
            "invoice_number",
            "invoice_date",
            "currency",
            "po_number",
            "subtotal",
            "tax",
            "total",
          ] as const
        ).map((key) => (
          <Field
            key={key}
            id={key}
            label={key.replaceAll("_", " ")}
            value={value[key]}
            error={errors[key]}
            onChange={(e) => change(key, e.target.value)}
          />
        ))}
      </div>
      <h3>Line items</h3>
      {value.items.map((line, i) => (
        <div className="edit-line" key={i}>
          {Object.entries(line).map(([key, val]) => (
            <Field
              key={key}
              id={`line-${i}-${key}`}
              label={key.replaceAll("_", " ")}
              value={val}
              error={errors[`line-${i}-${key}`]}
              onChange={(e) =>
                onChange({
                  ...value,
                  items: value.items.map((x, n) =>
                    n === i ? { ...x, [key]: e.target.value } : x,
                  ),
                })
              }
            />
          ))}
        </div>
      ))}
      {error && <Notice message={error} error />}
      <div className="dialog-actions">
        <Button onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" busy={busy}>
          Save verified revision
        </Button>
      </div>
    </form>
  );
}

function UploadDialog({
  onClose,
  onUploaded,
  live,
}: {
  onClose: () => void;
  onUploaded: (id: string) => void;
  live: boolean;
}) {
  const [file, setFile] = useState<File | null>(null),
    [mode, setMode] = useState(live ? "local" : "replay"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Choose a document first.");
      fileRef.current?.focus();
      return;
    }
    if (file.size === 0 || file.size > 10 * 1024 * 1024) {
      setError("Choose a non-empty file up to 10 MB.");
      return;
    }
    if (!/\.(pdf|png|jpe?g)$/i.test(file.name)) {
      setError("Choose a PDF, PNG or JPEG.");
      return;
    }
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("mode", mode);
    try {
      const result = await api<{ id: string; duplicate: boolean }>(
        "/invoices",
        { method: "POST", body: form },
      );
      onUploaded(result.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Upload a supplier invoice" onClose={onClose} busy={busy}>
      <form noValidate onSubmit={upload}>
        <div className="upload-zone">
          <Upload size={30} />
          <strong>Start with the source document</strong>
          <p>PDF, PNG or JPEG · up to 10 MB · 1–3 pages</p>
          <label className="field" htmlFor="invoice-file">
            <span>Choose document</span>
            <input
              id="invoice-file"
              ref={fileRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              disabled={busy}
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setError("");
              }}
            />
          </label>
        </div>
        <label className="field" htmlFor="extraction-mode">
          <span>Extraction mode</span>
          <select
            id="extraction-mode"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="local">Local AI — real model inference</option>
            <option value="replay">
              Recorded example — included fixtures only
            </option>
          </select>
        </label>
        <p className="help">
          {mode === "local"
            ? live
              ? "Local model is connected. The document stays on this machine."
              : "Local model is not connected. Start the model service before uploading."
            : "Replay only recognises the bundled example PDFs. It does not run an AI model."}
        </p>
        <Notice message={error} error={Boolean(error)} />
        <div className="dialog-actions">
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            Upload & check
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function Orders() {
  const [items, setItems] = useState<Order[]>([]),
    [error, setError] = useState(""),
    [filter, setFilter] = useState(""),
    [page, setPage] = useState(1);
  useEffect(() => {
    api<Order[]>("/orders")
      .then(setItems)
      .catch((e) => setError(e.message));
  }, []);
  const filtered = items.filter((x) =>
    (x.id + " " + x.supplier).toLowerCase().includes(filter.toLowerCase()),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Reference records</p>
          <h1>Purchase orders</h1>
          <p>Seeded orders and goods receipts used by the three-way check.</p>
        </div>
        <Badge status="matched">Synthetic reference data</Badge>
      </div>
      {error && <Notice message={error} error />}
      <div className="panel">
        <div className="panel-heading">
          <h2>Order register</h2>
          <div className="search">
            <Search size={16} />
            <input
              aria-label="Search purchase orders"
              placeholder="Find an order…"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                setPage(1);
              }}
            />
            {filter && (
              <button
                aria-label="Clear order search"
                onClick={() => {
                  setFilter("");
                  setPage(1);
                }}
              >
                <X size={15} />
              </button>
            )}
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <caption className="sr-only">
              Purchase orders, received quantities and prices
            </caption>
            <thead>
              <tr>
                <th>Order</th>
                <th>Supplier</th>
                <th>Receipt</th>
                <th>Ordered / received</th>
                <th>Unit price</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice((page - 1) * 10, page * 10).map((x) => (
                <tr key={x.id}>
                  <td className="mono">{x.id}</td>
                  <td>{x.supplier}</td>
                  <td className="mono">{x.receipt_id}</td>
                  <td>
                    {x.items[0].ordered} / {x.items[0].received} units
                  </td>
                  <td>{money(x.items[0].unit_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <div className="empty">No matching purchase orders.</div>
        )}
        <div className="pagination">
          <span>{filtered.length} orders · sandbox source</span>
          <nav aria-label="Order pages">
            <Button disabled={page === 1} onClick={() => setPage((x) => x - 1)}>
              Previous
            </Button>
            <span>Page {page}</span>
            <Button
              disabled={page * 10 >= filtered.length}
              onClick={() => setPage((x) => x + 1)}
            >
              Next
            </Button>
          </nav>
        </div>
      </div>
    </>
  );
}
function Drafts() {
  const [items, setItems] = useState<
      { name: string; reference: string; created: number; payload: Payload }[]
    >([]),
    [error, setError] = useState("");
  useEffect(() => {
    api<typeof items>("/drafts")
      .then(setItems)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Local integration sandbox</p>
          <h1>Draft register</h1>
          <p>
            Persisted demonstration drafts. These records are not ERPNext
            documents.
          </p>
        </div>
      </div>
      {error && <Notice message={error} error />}
      <div className="panel">
        {items.length === 0 ? (
          <div className="empty">
            <Workflow size={34} />
            <h2>No drafts yet</h2>
            <p>Approve a matched invoice, then create its sandbox draft.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <caption className="sr-only">
                Local sandbox draft invoices, latest 100
              </caption>
              <thead>
                <tr>
                  <th>Draft</th>
                  <th>Supplier</th>
                  <th>Invoice</th>
                  <th>Total</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {items.map((x) => (
                  <tr key={x.reference}>
                    <td className="mono">{x.name}</td>
                    <td>{x.payload.supplier}</td>
                    <td>{x.payload.invoice_number}</td>
                    <td>{money(x.payload.total)}</td>
                    <td>{timestamp(x.created)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="help">
        Latest 100 sandbox drafts. Unique import references protect this local
        destination against repeat creation.
      </p>
    </>
  );
}
function SystemPage({
  system,
  onRefresh,
}: {
  system: System | null;
  onRefresh: () => void;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Operational visibility</p>
          <h1>Know what’s running.</h1>
          <p>
            Actual service status and the boundaries of this portfolio build.
          </p>
        </div>
        <Button onClick={onRefresh}>
          <RefreshCw size={16} />
          Refresh status
        </Button>
      </div>
      {!system ? (
        <div className="empty">Checking local services…</div>
      ) : (
        <>
          <div className="system-grid">
            {[
              {
                title: "Document worker",
                ok: system.worker_online,
                detail:
                  "Persistent SQL jobs, atomic claims and expiring leases.",
              },
              {
                title: "Local language model",
                ok: system.llm_online,
                detail: system.model + " · inference through a local endpoint.",
              },
              {
                title: "Relational database",
                ok: true,
                detail:
                  system.database +
                  " · documents, revisions, jobs and audit events.",
              },
              {
                title: "ERPNext",
                ok: false,
                detail:
                  "Adapter implemented. A real ERPNext instance has not been verified on this machine.",
              },
            ].map((x) => (
              <section className="panel system-card" key={x.title}>
                <div className="system-card-head">
                  <Settings2 size={22} />
                  <Badge status={x.ok ? "matched" : "needs_review"}>
                    {x.ok ? "Connected" : "Not verified / offline"}
                  </Badge>
                </div>
                <h2>{x.title}</h2>
                <p>{x.detail}</p>
              </section>
            ))}
          </div>
          <div className="panel scope-panel">
            <h2>What this build demonstrates</h2>
            <div className="scope-columns">
              <div>
                <h3>Implemented workflow</h3>
                <ul>
                  <li>Original document and located source evidence</li>
                  <li>Decimal arithmetic and three-way invoice checks</li>
                  <li>Revision-bound human approval</li>
                  <li>Background processing and audit trail</li>
                  <li>Explicit sandbox draft creation</li>
                </ul>
              </div>
              <div>
                <h3>Deliberate limits</h3>
                <ul>
                  <li>One fictional company and EUR invoices</li>
                  <li>Zero-tax examples; no tax interpretation</li>
                  <li>No payment or invoice posting</li>
                  <li>Demo roles are not enterprise authentication</li>
                  <li>Real ERPNext integration awaits a live environment</li>
                </ul>
              </div>
            </div>
            <p className="help">
              Job states:{" "}
              {Object.entries(system.jobs)
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ") || "No jobs yet"}
            </p>
          </div>
        </>
      )}
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
