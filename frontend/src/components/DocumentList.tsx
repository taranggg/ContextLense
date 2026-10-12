import { Info, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { DocumentInfo } from "../api/types";
import { formatBytes, formatDate, plural } from "../lib/format";
import { Notice, StatusPill } from "./common";

function DocumentRow({ doc, onChange }: { doc: DocumentInfo; onChange: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChange();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  const meta = [
    doc.page_count != null && plural(doc.page_count, "page"),
    doc.chunk_count != null && doc.status === "ready" && plural(doc.chunk_count, "passage"),
    formatBytes(doc.size_bytes),
    `added ${formatDate(doc.created_at)}`,
  ].filter(Boolean);

  return (
    <li className="doc-row">
      <div className="doc-row-main">
        <div className="doc-row-title">
          {doc.status === "ready" ? <Link to={`/documents/${doc.id}`}>{doc.filename}</Link> : <span>{doc.filename}</span>}
          {doc.is_sample && <span className="tag" title="Bundled sample used by the research benchmark">Sample</span>}
        </div>
        <div className="doc-row-meta">
          {doc.status !== "ready" && (
            <>
              <StatusPill status={doc.status} /> ·{" "}
            </>
          )}
          {meta.join(" · ")}
        </div>
        {doc.status === "failed" && doc.error_message && <Notice tone="error">{doc.error_message}</Notice>}
        {doc.status === "ready" &&
          doc.warnings.map((w) => (
            <p key={w} className="doc-row-warning">
              <Info size={12} aria-hidden="true" />
              {w}
            </p>
          ))}
        {error && <Notice tone="error">{error}</Notice>}
      </div>
      <div className="doc-row-actions">
        {confirming ? (
          <>
            <span className="small muted">Delete document and its index?</span>
            <button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => run(() => api.deleteDocument(doc.id))}>
              Delete
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </>
        ) : (
          <>
            {doc.status === "ready" && (
              <Link to={`/documents/${doc.id}`} className="btn btn-secondary btn-sm">
                Open
              </Link>
            )}
            {doc.status === "failed" && doc.error_code !== "no_text" && (
              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => run(() => api.reprocessDocument(doc.id))}>
                <RotateCcw size={14} aria-hidden="true" /> Retry
              </button>
            )}
            <button
              type="button"
              className="icon-btn"
              aria-label={`Delete ${doc.filename}`}
              title="Delete"
              onClick={() => setConfirming(true)}
            >
              <Trash2 size={16} />
            </button>
          </>
        )}
      </div>
    </li>
  );
}

export function DocumentList({ documents, onChange }: { documents: DocumentInfo[]; onChange: () => void }) {
  if (!documents.length) {
    return <p className="empty">No documents yet. PDFs you upload will appear here.</p>;
  }
  return (
    <ul className="doc-list">
      {documents.map((doc) => (
        <DocumentRow key={doc.id} doc={doc} onChange={onChange} />
      ))}
    </ul>
  );
}
