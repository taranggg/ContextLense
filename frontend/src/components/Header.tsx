import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useReady } from "../lib/readiness";

const LLM_LABEL: Record<string, string> = {
  ready: "Model ready",
  loading: "Loading model",
  not_loaded: "Model idle",
  not_downloaded: "Model not downloaded",
  unavailable: "Model unavailable",
  not_configured: "Model not configured",
  error: "Model error",
};

function ModelStatus() {
  const { readiness, error } = useReady();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  let label = "Connecting…";
  let tone = "busy";
  if (error) {
    label = "Backend offline";
    tone = "bad";
  } else if (readiness) {
    const s = readiness.llm.status;
    label = LLM_LABEL[s] ?? s;
    tone = s === "ready" ? "ok" : s === "loading" || s === "not_loaded" ? "busy" : "bad";
  }

  return (
    <div className="model-status" ref={ref}>
      <button
        type="button"
        className="model-status-button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
      >
        <span className={`dot ${tone}`} aria-hidden="true" />
        <span className="model-status-label">{label}</span>
        <span className="visually-hidden">— show system status</span>
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="System status">
          {error ? (
            <p>{error.message}</p>
          ) : readiness ? (
            <dl className="status-rows">
              <dt>Local model</dt>
              <dd>
                <span className="mono">{readiness.llm.model}</span>
                <div className="muted">
                  {readiness.llm.runtime.toUpperCase()} · {LLM_LABEL[readiness.llm.status] ?? readiness.llm.status}
                  {readiness.llm.load_time_s != null && ` · loaded in ${readiness.llm.load_time_s}s`}
                </div>
                {readiness.llm.detail && <div className="muted">{readiness.llm.detail}</div>}
              </dd>
              <dt>Embeddings</dt>
              <dd>
                {readiness.embedding.detail}
                <div className="muted">{readiness.embedding.status.replace("_", " ")}</div>
              </dd>
              <dt>Storage</dt>
              <dd>{readiness.storage.detail}</dd>
              <dt>Privacy</dt>
              <dd className="muted">Documents and questions are processed on this machine. No hosted AI service is called.</dd>
            </dl>
          ) : (
            <p className="muted">Checking…</p>
          )}
        </div>
      )}
    </div>
  );
}

export function Header() {
  return (
    <header className="app-header">
      <Link to="/" className="wordmark" aria-label="ContextLens home">
        ContextLens
      </Link>
      <nav className="app-nav" aria-label="Main">
        <NavLink to="/" end>
          Documents
        </NavLink>
        <NavLink to="/research">Research</NavLink>
      </nav>
      <div className="header-spacer" />
      <ModelStatus />
    </header>
  );
}
