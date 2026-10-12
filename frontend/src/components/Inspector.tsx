import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ChatResponse, ChunkPage, DocumentInfo, RetrievedChunk } from "../api/types";
import { formatMs, formatPages } from "../lib/format";
import { Notice, Similarity } from "./common";

export type InspectorTab = "passages" | "details" | "document";

function Passage({ chunk, cited, focused }: { chunk: RetrievedChunk; cited: boolean; focused: boolean }) {
  const [expanded, setExpanded] = useState(focused);
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (focused) {
      setExpanded(true);
      ref.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }, [focused]);
  return (
    <li ref={ref} className={`passage${focused ? " focused" : ""}`} style={{ listStyle: "none" }}>
      <div className="passage-head">
        <span className="source-label">{chunk.source_label}</span>
        <span className="doc">{chunk.document_name}</span>
        <span className="muted">{formatPages(chunk.pages)}</span>
        {cited && <span className="tag">Cited</span>}
      </div>
      <div style={{ marginTop: 6 }}>
        <Similarity value={chunk.similarity} />
      </div>
      <p className={`passage-text${expanded ? "" : " clamped"}`}>{chunk.text}</p>
      <button type="button" className="link-btn small" style={{ marginTop: 6 }} onClick={() => setExpanded((e) => !e)}>
        {expanded ? "Show less" : "Show full passage"}
      </button>
    </li>
  );
}

function DocumentChunks({ documents }: { documents: DocumentInfo[] }) {
  const [docId, setDocId] = useState(documents[0]?.id);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<ChunkPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const limit = 10;

  useEffect(() => {
    if (!docId) return;
    let cancelled = false;
    setError(null);
    api
      .chunks(docId, offset, limit)
      .then((p) => !cancelled && setPage(p))
      .catch((err) => !cancelled && setError((err as ApiError).message));
    return () => {
      cancelled = true;
    };
  }, [docId, offset]);

  return (
    <div>
      {documents.length > 1 && (
        <select
          className="select"
          value={docId}
          aria-label="Document"
          onChange={(e) => {
            setDocId(e.target.value);
            setOffset(0);
          }}
          style={{ marginBottom: 12, width: "100%" }}
        >
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.filename}
            </option>
          ))}
        </select>
      )}
      <p className="small muted">
        Every passage indexed for this document, in reading order. The same passages are used for every question and every
        retrieval depth.
      </p>
      {error && <Notice tone="error">{error}</Notice>}
      {page && (
        <>
          <ul style={{ padding: 0, margin: "12px 0 0" }}>
            {page.chunks.map((c) => (
              <li key={c.chunk_id} className="passage" style={{ listStyle: "none" }}>
                <div className="passage-head">
                  <span className="tag">#{c.index + 1}</span>
                  <span className="muted">{formatPages(c.pages)}</span>
                  <span className="muted">{c.word_count} words</span>
                </div>
                <p className="passage-text clamped">{c.text}</p>
              </li>
            ))}
          </ul>
          <div className="pager">
            <button type="button" className="btn btn-ghost btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              Previous
            </button>
            <span className="muted tabular">
              {page.total ? `${offset + 1}–${Math.min(offset + limit, page.total)} of ${page.total}` : "No passages"}
            </span>
            <button type="button" className="btn btn-ghost btn-sm" disabled={offset + limit >= page.total} onClick={() => setOffset(offset + limit)}>
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}

interface Props {
  tab: InspectorTab;
  onTab: (tab: InspectorTab) => void;
  onClose: () => void;
  retrieved: RetrievedChunk[] | null;
  response: ChatResponse | null;
  focus: string | null;
  documents: DocumentInfo[];
}

export function Inspector({ tab, onTab, onClose, retrieved, response, focus, documents }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const cited = new Set(response?.citations.map((c) => c.source_label) ?? []);
  const tabs: [InspectorTab, string][] = retrieved
    ? [
        ["passages", "Retrieved passages"],
        ["details", "Details"],
        ["document", "All passages"],
      ]
    : [["document", "All passages"]];

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Source inspector">
        <div className="drawer-head">
          <h2>Source inspector</h2>
          <button ref={closeRef} type="button" className="icon-btn" onClick={onClose} aria-label="Close inspector">
            <X size={18} />
          </button>
        </div>
        <div className="tabs" role="tablist">
          {tabs.map(([key, label]) => (
            <button key={key} type="button" role="tab" className="tab" aria-selected={tab === key} onClick={() => onTab(key)}>
              {label}
            </button>
          ))}
        </div>
        <div className="drawer-body" role="tabpanel">
          {tab === "passages" && retrieved && (
            <>
              <p className="small muted" style={{ marginBottom: 12 }}>
                The passages given to the model for this answer, ranked by similarity to the question. Similarity measures how
                close a passage is to the question — it does not prove the passage supports the answer.
              </p>
              {response?.generation.context_truncated && (
                <Notice tone="warn">
                  To fit the model's context window, only {response.generation.sources_in_prompt} of {retrieved.length} passages
                  were included (the last one may be shortened).
                </Notice>
              )}
              <ul style={{ padding: 0, margin: 0 }}>
                {retrieved.map((chunk) => (
                  <Passage key={chunk.chunk_id} chunk={chunk} cited={cited.has(chunk.source_label)} focused={focus === chunk.source_label} />
                ))}
              </ul>
            </>
          )}
          {tab === "details" && response && (
            <>
              <section className="drawer-section">
                <h3>Timing</h3>
                <dl className="kv">
                  <dt>Retrieval</dt>
                  <dd className="tabular">{formatMs(response.latency.retrieval_ms)}</dd>
                  <dt>Generation</dt>
                  <dd className="tabular">{formatMs(response.latency.generation_ms)}</dd>
                  <dt>Total</dt>
                  <dd className="tabular">{formatMs(response.latency.total_ms)}</dd>
                </dl>
              </section>
              <section className="drawer-section">
                <h3>Generation</h3>
                <dl className="kv">
                  <dt>Model</dt>
                  <dd className="mono">{response.model.model}</dd>
                  <dt>Runtime</dt>
                  <dd>{response.model.runtime.toUpperCase()}</dd>
                  <dt>Temperature</dt>
                  <dd>{response.model.temperature}</dd>
                  <dt>Passages (K)</dt>
                  <dd>
                    {response.k} requested · {response.retrieved.length} retrieved · {response.generation.sources_in_prompt} in prompt
                  </dd>
                  <dt>Prompt tokens</dt>
                  <dd className="tabular">{response.generation.prompt_tokens?.toLocaleString() ?? "—"}</dd>
                  <dt>Answer tokens</dt>
                  <dd className="tabular">{response.generation.completion_tokens?.toLocaleString() ?? "—"}</dd>
                  <dt>Stopped because</dt>
                  <dd>
                    {response.generation.finish_reason === "length"
                      ? "token limit reached (answer may be cut off)"
                      : response.generation.finish_reason ?? "—"}
                  </dd>
                </dl>
              </section>
              <section className="drawer-section">
                <h3>Citations</h3>
                <p className="small">
                  {response.citations.length} of {response.retrieved.length} passages cited.
                  {response.invalid_citations.length > 0 &&
                    ` The answer also contains ${response.invalid_citations.join(", ")}, which do not match any supplied passage.`}
                </p>
              </section>
            </>
          )}
          {tab === "document" && <DocumentChunks documents={documents} />}
        </div>
      </aside>
    </>
  );
}
