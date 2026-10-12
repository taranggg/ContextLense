import { AlertTriangle, ChevronDown, ChevronRight, RotateCcw } from "lucide-react";
import { useState } from "react";
import type { ChatResponse, Citation, RetrievedChunk } from "../api/types";
import { formatMs, formatPages, plural } from "../lib/format";
import { AnswerText } from "./AnswerText";
import { Notice } from "./common";
import { Button } from "@/components/ui/button";

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
      <button
        type="button"
        className="grid w-full grid-cols-[auto_1fr] gap-3 rounded-lg border border-border bg-card p-3.5 text-left transition-colors hover:border-foreground/20"
        onClick={onOpen}
      >
        <span className="grid h-5 min-w-[26px] place-items-center rounded-md bg-accent px-1.5 text-[11px] font-semibold text-accent-foreground">
          {citation.source_label}
        </span>
        <span>
          <span className="break-words text-[13px] font-medium text-foreground">
            {citation.document_name} <span className="font-normal text-muted-foreground">· {formatPages(citation.excerpt_pages)}</span>
            {spansMore && <span className="text-xs font-normal text-muted-foreground"> (passage spans {formatPages(citation.pages)})</span>}
          </span>
          <span className="mt-1 block text-sm leading-normal text-foreground/80">“{citation.excerpt}”</span>
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
    <div className="animate-fade-in-up [&+&]:mt-7">
      <div className="flex justify-end">
        <div className="max-w-[82%] whitespace-pre-wrap break-words rounded-[20px] bg-secondary px-4 py-2.5">{turn.question}</div>
      </div>
      <div className="mt-7" aria-live={turn.status === "done" ? undefined : "polite"}>
        {turn.status === "retrieving" && (
          <div className="flex items-center gap-2.5 text-[15px] text-muted-foreground">
            <span className="size-3.5 shrink-0 animate-spin rounded-full border-2 border-secondary border-t-foreground/60" aria-hidden="true" /> Searching
            the document…
          </div>
        )}
        {turn.status === "generating" && !turn.partial && (
          <div className="flex items-center gap-2.5 text-[15px] text-muted-foreground">
            <span className="size-3.5 shrink-0 animate-spin rounded-full border-2 border-secondary border-t-foreground/60" aria-hidden="true" /> Reading{" "}
            {plural(retrieved.length, "passage")}…
          </div>
        )}

        {response?.abstained && (
          <div className="mb-1.5 inline-flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
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
                <Button variant="secondary" size="sm" onClick={onRetry}>
                  <RotateCcw size={14} aria-hidden="true" /> Try again
                </Button>
              )
            }
          >
            {turn.error.message}
          </Notice>
        )}

        {response && response.citations.length > 0 && (
          <div className="mt-4">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 py-1 text-[13px] font-medium text-foreground/80 hover:text-foreground"
              aria-expanded={sourcesOpen}
              onClick={() => setSourcesOpen((o) => !o)}
            >
              {sourcesOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              Sources ({response.citations.length})
            </button>
            {sourcesOpen && (
              <ul className="mt-2 grid list-none gap-2 p-0">
                {response.citations.map((c) => (
                  <SourceItem key={c.source_label} citation={c} onOpen={() => onInspect(c.source_label)} />
                ))}
              </ul>
            )}
          </div>
        )}

        {response && !response.abstained && response.citations.length === 0 && !response.cancelled && (
          <div className="mt-3">
            <Notice tone="warn">This answer has no citations. Check the retrieved passages before relying on it.</Notice>
          </div>
        )}

        {(response || turn.status === "cancelled") && (
          <div className="mt-3 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-xs text-muted-foreground">
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
              <button type="button" className="border-none bg-none p-0 text-primary hover:underline" onClick={() => onInspect(null)}>
                Inspect retrieval
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
