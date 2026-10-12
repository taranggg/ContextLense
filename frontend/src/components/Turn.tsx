import { AlertTriangle, ChevronDown, ChevronRight, RotateCcw } from "lucide-react";
import { useState } from "react";
import type { ChatResponse, Citation, RetrievedChunk } from "../api/types";
import { formatMs, formatPages, plural } from "../lib/format";
import { AnswerText } from "./AnswerText";
import { Notice } from "./common";

export interface ChatTurn {
  id: string;
  question: string;
  k: number;
  status: "retrieving" | "generating" | "done" | "error" | "cancelled";
  partial: string;
  retrieved?: RetrievedChunk[];
  response?: ChatResponse;
  error?: { code: string; message: string };
}

function SourceItem({ citation, onOpen }: { citation: Citation; onOpen: () => void }) {
  const spansMore = citation.pages.length > citation.excerpt_pages.length;
  return (
    <li>
      <button type="button" className="source-item" onClick={onOpen}>
        <span className="source-label">{citation.source_label}</span>
        <span>
          <span className="source-head">
            {citation.document_name} <span className="muted">· {formatPages(citation.excerpt_pages)}</span>
            {spansMore && <span className="muted small"> (passage spans {formatPages(citation.pages)})</span>}
          </span>
          <span className="excerpt" style={{ display: "block" }}>
            “{citation.excerpt}”
          </span>
        </span>
      </button>
    </li>
  );
}

interface Props {
  turn: ChatTurn;
  onInspect: (focus: string | null) => void;
  onRetry: () => void;
}

export function Turn({ turn, onInspect, onRetry }: Props) {
  const [sourcesOpen, setSourcesOpen] = useState(true);
  const response = turn.response;
  const retrieved = response?.retrieved ?? turn.retrieved ?? [];
  const validLabels = new Set(
    (response ? retrieved.slice(0, response.generation.sources_in_prompt) : retrieved).map((c) => c.source_label),
  );
  const text = response?.answer ?? turn.partial;

  return (
    <>
      <div className="msg msg-user">
        <div className="bubble">{turn.question}</div>
      </div>
      <div className="msg msg-assistant" aria-live={turn.status === "done" ? undefined : "polite"}>
        {turn.status === "retrieving" && (
          <div className="thinking">
            <span className="spinner" aria-hidden="true" /> Searching the document…
          </div>
        )}
        {turn.status === "generating" && !turn.partial && (
          <div className="thinking">
            <span className="spinner" aria-hidden="true" /> Reading {plural(retrieved.length, "passage")}…
          </div>
        )}

        {response?.abstained && (
          <div className="abstain">
            <AlertTriangle size={13} aria-hidden="true" /> Not enough evidence in the selected documents
          </div>
        )}

        {text && (
          <AnswerText
            text={text}
            validLabels={validLabels}
            streaming={turn.status === "generating"}
            onCite={(label) => onInspect(label)}
          />
        )}

        {turn.status === "error" && turn.error && (
          <Notice
            tone="error"
            actions={
              turn.error.code !== "document_not_found" && (
                <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
                  <RotateCcw size={14} aria-hidden="true" /> Try again
                </button>
              )
            }
          >
            {turn.error.message}
          </Notice>
        )}

        {response && response.citations.length > 0 && (
          <div className="sources">
            <button type="button" className="sources-toggle" aria-expanded={sourcesOpen} onClick={() => setSourcesOpen((o) => !o)}>
              {sourcesOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              Sources ({response.citations.length})
            </button>
            {sourcesOpen && (
              <ul className="source-list">
                {response.citations.map((c) => (
                  <SourceItem key={c.source_label} citation={c} onOpen={() => onInspect(c.source_label)} />
                ))}
              </ul>
            )}
          </div>
        )}

        {response && !response.abstained && response.citations.length === 0 && !response.cancelled && (
          <div style={{ marginTop: 12 }}>
            <Notice tone="warn">This answer has no citations. Check the retrieved passages before relying on it.</Notice>
          </div>
        )}

        {(response || turn.status === "cancelled") && (
          <div className="msg-meta">
            {turn.status === "cancelled" && <span>Stopped</span>}
            {response && (
              <>
                <span>
                  From {plural(response.generation.sources_in_prompt, "passage")} · {formatMs(response.latency.total_ms)}
                </span>
                {response.generation.finish_reason === "length" && <span>Answer reached the length limit</span>}
                {response.invalid_citations.length > 0 && (
                  <span title="The model produced citation markers that do not match any passage it was given.">
                    {plural(response.invalid_citations.length, "unmatched citation")}
                  </span>
                )}
              </>
            )}
            {retrieved.length > 0 && (
              <button type="button" className="link-btn" onClick={() => onInspect(null)}>
                Inspect retrieval
              </button>
            )}
          </div>
        )}
      </div>
    </>
  );
}
