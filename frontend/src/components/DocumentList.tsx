import { Info, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { DocumentInfo } from "../api/types";
import { formatBytes, formatDate, plural } from "../lib/format";
import { Notice, StatusPill } from "./common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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
    <li className="grid grid-cols-[1fr_auto] items-center gap-4 border-b border-border py-4 first:border-t max-sm:grid-cols-1">
      <div className="min-w-0">
        <div className="flex items-center gap-2 font-medium break-words">
          {doc.status === "ready" ? (
            <Link className="min-w-0 break-words text-foreground" to={`/documents/${doc.id}`}>{doc.filename}</Link>
          ) : (
            <span className="min-w-0 break-words">{doc.filename}</span>
          )}
          {doc.is_sample && <Badge title="Bundled sample used by the research benchmark">Sample</Badge>}
        </div>
        <div className="mt-0.5 text-[13px] text-muted-foreground">
          {doc.status !== "ready" && (
            <>
              <StatusPill status={doc.status} /> ·{" "}
            </>
          )}
          {meta.join(" · ")}
        </div>
        {doc.status === "failed" && doc.error_message && (
          <div className="mt-2.5">
            <Notice tone="error">{doc.error_message}</Notice>
          </div>
        )}
        {doc.status === "ready" &&
          doc.warnings.map((w) => (
            <p key={w} className="mt-1 flex items-start gap-1.5 text-xs text-muted-foreground">
              <Info size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
              {w}
            </p>
          ))}
        {error && (
          <div className="mt-2.5">
            <Notice tone="error">{error}</Notice>
          </div>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        {confirming ? (
          <>
            <span className="text-sm text-muted-foreground">Delete document and its index?</span>
            <Button variant="destructive" size="sm" disabled={busy} onClick={() => run(() => api.deleteDocument(doc.id))}>
              Delete
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            {doc.status === "ready" && (
              <Button asChild variant="secondary" size="sm">
                <Link to={`/documents/${doc.id}`}>Open</Link>
              </Button>
            )}
            {doc.status === "failed" && doc.error_code !== "no_text" && (
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => run(() => api.reprocessDocument(doc.id))}>
                <RotateCcw size={14} aria-hidden="true" /> Retry
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Delete ${doc.filename}`}
              title="Delete"
              onClick={() => setConfirming(true)}
            >
              <Trash2 size={16} />
            </Button>
          </>
        )}
      </div>
    </li>
  );
}

export function DocumentList({ documents, onChange }: { documents: DocumentInfo[]; onChange: () => void }) {
  if (!documents.length) {
    return <p className="py-10 text-center text-[15px] text-muted-foreground">No documents yet. PDFs you upload will appear here.</p>;
  }
  return (
    <ul className="m-0 list-none p-0">
      {documents.map((doc) => (
        <DocumentRow key={doc.id} doc={doc} onChange={onChange} />
      ))}
    </ul>
  );
}
