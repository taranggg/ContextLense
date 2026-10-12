import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ChatResponse, ChunkPage, DocumentInfo, RetrievedChunk } from "../api/types";
import { formatMs, formatPages } from "../lib/format";
import { Notice, Similarity } from "./common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

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
    <li
      ref={ref}
      className={cn(
        "list-none border-b border-border py-3.5 first:pt-1",
        focused && "-mx-3 rounded-lg border-b-transparent bg-accent px-3 py-3.5",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[13px]">
        <span className="grid h-5 min-w-[26px] place-items-center rounded-md bg-accent px-1.5 text-[11px] font-semibold text-accent-foreground">
          {chunk.source_label}
        </span>
        <span className="break-words font-medium">{chunk.document_name}</span>
        <span className="text-muted-foreground">{formatPages(chunk.pages)}</span>
        {cited && <Badge>Cited</Badge>}
      </div>
      <div className="mt-1.5">
        <Similarity value={chunk.similarity} />
      </div>
      <p className={cn("mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/80", !expanded && "line-clamp-6")}>
        {chunk.text}
      </p>
      <button type="button" className="mt-1.5 border-none bg-none p-0 text-sm text-primary hover:underline" onClick={() => setExpanded((e) => !e)}>
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
        <Select
          value={docId}
          aria-label="Document"
          className="mb-3 w-full"
          onChange={(e) => {
            setDocId(e.target.value);
            setOffset(0);
          }}
        >
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.filename}
            </option>
          ))}
        </Select>
      )}
      <p className="text-sm text-muted-foreground">
        Every passage indexed for this document, in reading order. The same passages are used for every question and every
        retrieval depth.
      </p>
      {error && <Notice tone="error">{error}</Notice>}
      {page && (
        <>
          <ul className="m-0 mt-3 list-none p-0">
            {page.chunks.map((c) => (
              <li key={c.chunk_id} className="list-none border-b border-border py-3.5">
                <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[13px]">
                  <Badge>#{c.index + 1}</Badge>
                  <span className="text-muted-foreground">{formatPages(c.pages)}</span>
                  <span className="text-muted-foreground">{c.word_count} words</span>
                </div>
                <p className="mt-2 line-clamp-6 whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/80">{c.text}</p>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex items-center justify-between text-sm">
            <Button variant="ghost" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              Previous
            </Button>
            <span className="tabular-nums text-muted-foreground">
              {page.total ? `${offset + 1}–${Math.min(offset + limit, page.total)} of ${page.total}` : "No passages"}
            </span>
            <Button variant="ghost" size="sm" disabled={offset + limit >= page.total} onClick={() => setOffset(offset + limit)}>
              Next
            </Button>
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
  const cited = new Set(response?.citations.map((c) => c.source_label) ?? []);
  const tabs: [InspectorTab, string][] = retrieved
    ? [
        ["passages", "Retrieved passages"],
        ["details", "Details"],
        ["document", "All passages"],
      ]
    : [["document", "All passages"]];

  return (
    <Sheet open onOpenChange={(open) => !open && onClose()}>
      <SheetContent aria-label="Source inspector" className="gap-0 p-0">
        <SheetHeader>
          <SheetTitle>Source inspector</SheetTitle>
        </SheetHeader>
        <div className="flex gap-1 border-b border-border px-4 pt-2.5" role="tablist">
          {tabs.map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              className={cn(
                "-mb-px border-b-2 border-transparent px-2.5 py-2 text-[13px] text-muted-foreground",
                tab === key && "border-foreground font-medium text-foreground",
              )}
              onClick={() => onTab(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 pb-8" role="tabpanel">
          {tab === "passages" && retrieved && (
            <>
              <p className="mb-3 text-sm text-muted-foreground">
                The passages given to the model for this answer, ranked by similarity to the question. Similarity measures how
                close a passage is to the question — it does not prove the passage supports the answer.
              </p>
              {response?.generation.context_truncated && (
                <Notice tone="warn">
                  To fit the model's context window, only {response.generation.sources_in_prompt} of {retrieved.length} passages
                  were included (the last one may be shortened).
                </Notice>
              )}
              <ul className="m-0 list-none p-0">
                {retrieved.map((chunk) => (
                  <Passage key={chunk.chunk_id} chunk={chunk} cited={cited.has(chunk.source_label)} focused={focus === chunk.source_label} />
                ))}
              </ul>
            </>
          )}
          {tab === "details" && response && (
            <>
              <section>
                <h3 className="mb-2.5 text-[13px] font-semibold">Timing</h3>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
                  <dt className="text-muted-foreground">Retrieval</dt>
                  <dd className="tabular-nums">{formatMs(response.latency.retrieval_ms)}</dd>
                  <dt className="text-muted-foreground">Generation</dt>
                  <dd className="tabular-nums">{formatMs(response.latency.generation_ms)}</dd>
                  <dt className="text-muted-foreground">Total</dt>
                  <dd className="tabular-nums">{formatMs(response.latency.total_ms)}</dd>
                </dl>
              </section>
              <section className="mt-6">
                <h3 className="mb-2.5 text-[13px] font-semibold">Generation</h3>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
                  <dt className="text-muted-foreground">Model</dt>
                  <dd className="font-mono text-[0.86em]">{response.model.model}</dd>
                  <dt className="text-muted-foreground">Runtime</dt>
                  <dd>{response.model.runtime.toUpperCase()}</dd>
                  <dt className="text-muted-foreground">Temperature</dt>
                  <dd>{response.model.temperature}</dd>
                  <dt className="text-muted-foreground">Passages (K)</dt>
                  <dd>
                    {response.k} requested · {response.retrieved.length} retrieved · {response.generation.sources_in_prompt} in prompt
                  </dd>
                  <dt className="text-muted-foreground">Prompt tokens</dt>
                  <dd className="tabular-nums">{response.generation.prompt_tokens?.toLocaleString() ?? "—"}</dd>
                  <dt className="text-muted-foreground">Answer tokens</dt>
                  <dd className="tabular-nums">{response.generation.completion_tokens?.toLocaleString() ?? "—"}</dd>
                  <dt className="text-muted-foreground">Stopped because</dt>
                  <dd>
                    {response.generation.finish_reason === "length"
                      ? "token limit reached (answer may be cut off)"
                      : response.generation.finish_reason ?? "—"}
                  </dd>
                </dl>
              </section>
              <section className="mt-6">
                <h3 className="mb-2.5 text-[13px] font-semibold">Citations</h3>
                <p className="text-sm">
                  {response.citations.length} of {response.retrieved.length} passages cited.
                  {response.invalid_citations.length > 0 &&
                    ` The answer also contains ${response.invalid_citations.join(", ")}, which do not match any supplied passage.`}
                </p>
              </section>
            </>
          )}
          {tab === "document" && <DocumentChunks documents={documents} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}
