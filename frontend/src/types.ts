export type Line = {
  sku: string;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
};
export type Payload = {
  supplier: string;
  invoice_number: string;
  invoice_date: string;
  currency: string;
  po_number: string;
  subtotal: string;
  tax: string;
  total: string;
  items: Line[];
};
export type Issue = {
  code: string;
  title: string;
  detail: string;
  field: string;
  line: number | null;
  severity: string;
};
export type Evidence = {
  text: string;
  page: number;
  box?: number[];
  manual?: boolean;
};
export type Order = {
  id: string;
  supplier: string;
  currency: string;
  source: string;
  receipt_id: string;
  items: {
    sku: string;
    description: string;
    ordered: string;
    received: string;
    unit_price: string;
  }[];
};
export type Invoice = {
  id: string;
  filename: string;
  status: string;
  version: number;
  revision: number;
  created: number;
  updated: number;
  mode: string;
  payload: Payload | null;
  issues: Issue[];
  evidence: Record<string, Evidence>;
  pages: number;
  error: string | null;
  elapsed: number | null;
  remote_id: string | null;
  source_engine: string | null;
  order: Order | null;
  events: {
    id: string;
    action: string;
    actor: string;
    detail: string;
    created: number;
  }[];
  revisions: {
    id: string;
    revision: number;
    actor: string;
    payload: Payload;
    created: number;
  }[];
};
export type Queue = {
  items: Invoice[];
  total: number;
  page: number;
  page_size: number;
  counts: Record<string, number>;
};
export type System = {
  erp_mode: string;
  database: string;
  llm_online: boolean;
  model: string;
  worker_online: boolean;
  jobs: Record<string, number>;
  demo_auth: boolean;
  erp_verified: boolean;
  build: string;
};
export type User = { role: string; demo: boolean };
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    credentials: "same-origin",
    headers:
      options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
    signal: options.signal ?? AbortSignal.timeout(30000),
  });
  if (!response.ok) {
    if (response.status === 401 && path !== "/login" && path !== "/me") {
      window.dispatchEvent(new Event("matchbook:session-expired"));
    }
    const body = await response
      .json()
      .catch(() => ({ detail: "Service unavailable. Try again." }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Check the entered values and try again.",
    );
  }
  return response.json();
}
export const money = (value: string | number | undefined) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "EUR" }).format(
    Number(value ?? 0),
  );
export const timestamp = (seconds: number) =>
  new Date(seconds * 1000).toLocaleString("en-GB", {
    timeZone: "UTC",
    dateStyle: "medium",
    timeStyle: "short",
  }) + " UTC";
export const labels: Record<string, string> = {
  queued: "Queued",
  processing: "Processing",
  needs_review: "Needs review",
  approved: "Approved",
  syncing: "Creating draft",
  synced: "Draft created",
  failed: "Failed",
  sync_uncertain: "Sync on hold",
};
