import { Check, FileText, FileUp, X } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, uploadDocuments } from "../api/client";
import type { DocumentInfo } from "../api/types";
import { formatBytes, plural } from "../lib/format";
import { isProcessing } from "../lib/hooks";
import { Notice, PIPELINE_STEPS, StatusPill } from "./common";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

/** One file in the current batch: rejected before upload, rejected by the server, or a document being processed. */
interface Item {
  key: string;
  name: string;
  size: number;
  doc?: DocumentInfo;
  error?: string;
}

type State =
  | { phase: "idle"; message?: string }
  | { phase: "uploading"; items: Item[]; progress: number; abort: () => void }
  | { phase: "tracking"; items: Item[] };

const workspaceUrl = (ids: string[]) =>
  `/documents/${ids[0]}${ids.length > 1 ? `?with=${ids.slice(1).join(",")}` : ""}`;

export function Uploader({ maxMb, maxFiles, onChange }: { maxMb: number; maxFiles: number; onChange: () => void }) {
  const [state, setState] = useState<State>({ phase: "idle" });
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const tracking = state.phase === "tracking" ? state : null;
  const pending = tracking?.items.some((i) => i.doc && isProcessing(i.doc)) ?? false;

  // Poll documents that are still processing.
  useEffect(() => {
    if (!tracking || !pending) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const docs = await api.listDocuments();
        if (cancelled) return;
        const byId = new Map(docs.map((d) => [d.id, d]));
        const items = tracking.items.map((i) =>
          i.doc ? { ...i, doc: byId.get(i.doc.id) ?? { ...i.doc, status: "failed" as const, error_message: "This document was deleted." } } : i,
        );
        const stillPending = items.some((i) => i.doc && isProcessing(i.doc));
        if (!stillPending) {
          onChange();
          const ready = items.filter((i) => i.doc?.status === "ready").map((i) => i.doc!.id);
          const problems = items.some((i) => i.error || (i.doc && i.doc.status !== "ready"));
          if (ready.length && !problems) {
            navigate(workspaceUrl(ready));
            return;
          }
        }
        setState({ phase: "tracking", items });
      } catch (err) {
        if (!cancelled) setState({ phase: "idle", message: (err as ApiError).message });
      }
    }, 800);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [tracking, pending, navigate, onChange]);

  const start = (fileList: File[]) => {
    if (!fileList.length) return;
    if (fileList.length > maxFiles) {
      setState({ phase: "idle", message: `You can upload up to ${maxFiles} PDFs at a time. You selected ${fileList.length}.` });
      return;
    }
    const items: Item[] = fileList.map((f, i) => ({ key: `${i}-${f.name}`, name: f.name, size: f.size }));
    const valid: File[] = [];
    fileList.forEach((file, i) => {
      if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type !== "application/pdf")) {
        items[i].error = "Not a PDF file.";
      } else if (file.size > maxMb * 1024 * 1024) {
        items[i].error = `Larger than the ${maxMb} MB limit.`;
      } else {
        valid.push(file);
      }
    });
    if (!valid.length) {
      setState({ phase: "tracking", items });
      return;
    }

    const { promise, abort } = uploadDocuments(valid, (progress) =>
      setState((s) => (s.phase === "uploading" ? { ...s, progress } : s)),
    );
    setState({ phase: "uploading", items, progress: 0, abort });
    promise
      .then((result) => {
        onChange();
        // The server keeps upload order within `documents` and within `errors`, so match in order.
        const docs = [...result.documents];
        const errors = [...result.errors];
        const merged = items.map((item): Item => {
          if (item.error) return item;
          if (errors[0] && errors[0].filename === item.name && docs[0]?.filename !== item.name) {
            return { ...item, error: errors.shift()!.message };
          }
          const doc = docs.shift();
          return doc ? { ...item, doc } : { ...item, error: errors.shift()?.message ?? "Upload failed." };
        });
        setState({ phase: "tracking", items: merged });
      })
      .catch((err) => {
        if ((err as Error).name === "AbortError") setState({ phase: "idle" });
        else setState({ phase: "idle", message: (err as ApiError).message });
      });
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (state.phase === "uploading" || pending) return;
    start(Array.from(e.dataTransfer.files));
  };

  const items = state.phase === "idle" ? [] : state.items;
  const busy = state.phase === "uploading" || pending;
  const finished = state.phase === "tracking" && !pending;
  const readyIds = items.filter((i) => i.doc?.status === "ready").map((i) => i.doc!.id);

  // Pipeline steps are shown when a single document is in flight.
  const single = items.length === 1 ? items[0] : null;
  const currentKey = state.phase === "uploading" ? "uploading" : single?.doc?.status;
  const currentIndex = PIPELINE_STEPS.findIndex((s) => s.key === (currentKey === "queued" ? "extracting" : currentKey));

  const browse = (
    <Button variant="secondary" onClick={() => input.current?.click()} disabled={busy}>
      Browse files
    </Button>
  );

  return (
    <div
      className={cn(
        "mt-12 flex min-h-[260px] flex-col items-center justify-center gap-3 rounded-2xl border-[1.5px] border-dashed border-border bg-card p-10 text-center transition-colors",
        dragging && "border-primary bg-accent",
      )}
      onDragOver={(e) => {
        e.preventDefault();
        if (!busy) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = "";
          start(files);
        }}
      />

      {items.length > 0 ? (
        <div className="w-full max-w-[520px] text-left" aria-live="polite">
          <ul className="m-0 grid list-none gap-2.5 p-0">
            {items.map((item) => (
              <li key={item.key}>
                <div className="flex items-center gap-2.5 text-[15px] font-medium">
                  <FileText size={18} className="shrink-0" aria-hidden="true" />
                  <span className="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap">{item.name}</span>
                  <span className="shrink-0 text-xs font-normal text-muted-foreground">{formatBytes(item.size)}</span>
                  <span className="shrink-0 text-xs font-normal">
                    {item.error ? (
                      <span className="text-destructive">Not uploaded</span>
                    ) : item.doc ? (
                      <StatusPill status={item.doc.status} />
                    ) : (
                      <span className="text-muted-foreground">Uploading…</span>
                    )}
                  </span>
                </div>
                {(item.error || (item.doc?.status === "failed" && item.doc.error_message)) && (
                  <p className="ml-7 mt-0.5 text-[13px] text-destructive">{item.error ?? item.doc?.error_message}</p>
                )}
              </li>
            ))}
          </ul>

          {state.phase === "uploading" && (
            <div className="mt-4 flex items-center gap-2">
              <Progress value={Math.round(state.progress * 100)} className="flex-1" />
              <Button variant="ghost" size="icon" onClick={state.abort} aria-label="Cancel upload">
                <X size={16} />
              </Button>
            </div>
          )}
          {state.phase === "tracking" && pending && (
            <div className="mt-4">
              <Progress indeterminate />
            </div>
          )}

          {single && !single.error && busy && (
            <ol className="m-0 mt-3.5 flex flex-wrap gap-x-4 gap-y-1 p-0 text-[13px] text-muted-foreground">
              {PIPELINE_STEPS.map((step, i) => (
                <li
                  key={step.key}
                  className={cn("inline-flex items-center gap-1.5", i < currentIndex && "text-foreground/80", i === currentIndex && "font-medium text-foreground")}
                >
                  {i < currentIndex && <Check size={13} aria-hidden="true" />}
                  {step.label}
                </li>
              ))}
            </ol>
          )}

          {finished && (
            <div className="mt-4.5 flex justify-end gap-2">
              {readyIds.length > 0 && (
                <Button size="sm" onClick={() => navigate(workspaceUrl(readyIds))}>
                  Open {readyIds.length > 1 ? plural(readyIds.length, "document") : "document"}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => setState({ phase: "idle" })}>
                Upload more
              </Button>
            </div>
          )}
        </div>
      ) : (
        <>
          <FileUp size={32} strokeWidth={1.5} className="text-muted-foreground" aria-hidden="true" />
          <p className="text-[19px] font-medium">Drop PDFs here</p>
          {browse}
          <p className="text-[13px] text-muted-foreground">
            Up to {maxFiles} PDFs at a time · {maxMb} MB each · selectable text only (scanned pages are not supported)
          </p>
          {state.phase === "idle" && state.message && (
            <div className="mt-3 w-full max-w-[520px]">
              <Notice tone="error">{state.message}</Notice>
            </div>
          )}
        </>
      )}
    </div>
  );
}
