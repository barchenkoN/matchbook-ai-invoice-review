import {
  useEffect,
  useRef,
  type ButtonHTMLAttributes,
  type ReactNode,
  type InputHTMLAttributes,
} from "react";
import { Check, AlertTriangle, Clock, LoaderCircle, X } from "lucide-react";
import { labels } from "./types";

export function Button({
  children,
  busy = false,
  variant = "outline",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  busy?: boolean;
  variant?: string;
}) {
  return (
    <button
      {...props}
      type={props.type ?? "button"}
      className={`button ${variant} ${props.className ?? ""}`}
      disabled={props.disabled || busy}
      aria-busy={busy}
      data-initial-focus={props.autoFocus || undefined}
    >
      {busy ? <LoaderCircle size={16} className="spin" /> : null}
      {children}
    </button>
  );
}
export function Badge({
  status,
  children,
}: {
  status: string;
  children?: ReactNode;
}) {
  const good = ["synced", "approved", "matched"].includes(status);
  const warn = ["needs_review", "sync_uncertain"].includes(status);
  return (
    <span
      className={`badge ${good ? "good" : warn ? "warn" : status === "failed" ? "bad" : "neutral"}`}
    >
      {good ? (
        <Check size={12} />
      ) : warn ? (
        <AlertTriangle size={12} />
      ) : (
        <Clock size={12} />
      )}{" "}
      {children ?? labels[status] ?? status}
    </span>
  );
}
export function Notice({
  message,
  error = false,
}: {
  message: string;
  error?: boolean;
}) {
  return (
    <div
      className={`notice ${error ? "error" : ""}`}
      role={error ? "alert" : "status"}
      aria-live="polite"
    >
      {message}
    </div>
  );
}
export function Field({
  label,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  return (
    <label className="field" htmlFor={props.id}>
      <span>{label}</span>
      <input
        {...props}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? props.id + "-error" : undefined}
      />
      {error ? (
        <small id={props.id + "-error"} className="field-error">
          {error}
        </small>
      ) : null}
    </label>
  );
}
export function Modal({
  title,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.showModal();
    ref.current
      ?.querySelector<HTMLElement>("[data-initial-focus=true]")
      ?.focus();
    return () => {
      ref.current?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) closeRef.current();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-head">
        <h2 id="modal-title">{title}</h2>
        <Button aria-label="Close dialog" disabled={busy} onClick={onClose}>
          <X size={18} />
        </Button>
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
