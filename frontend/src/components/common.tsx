import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import type { ReactNode } from "react";
import type { DocumentInfo } from "../api/types";
import { cn } from "@/lib/utils";

const NOTICE_TONE = {
  neutral: "bg-muted text-muted-foreground",
  error: "bg-destructive/10 text-destructive",
  warn: "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
  info: "bg-accent text-accent-foreground",
} as const;

export function Notice({
  tone = "neutral",
  children,
  actions,
}: {
  tone?: "neutral" | "error" | "warn" | "info";
  children: ReactNode;
  actions?: ReactNode;
}) {
  const Icon = tone === "error" ? AlertCircle : tone === "warn" ? AlertTriangle : Info;
  return (
    <div
      className={cn("flex items-start gap-2.5 rounded-lg px-3.5 py-3 text-sm leading-relaxed", NOTICE_TONE[tone])}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div>
        {children}
        {actions && <div className="mt-2 flex gap-2">{actions}</div>}
      </div>
    </div>
  );
}

const STATUS_TEXT: Record<DocumentInfo["status"], string> = {
  queued: "Queued",
  extracting: "Extracting text",
  chunking: "Splitting into passages",
  embedding: "Embedding",
  indexing: "Indexing",
  ready: "Ready",
  failed: "Failed",
};

const DOT_TONE = {
  ok: "bg-emerald-500",
  busy: "bg-primary animate-pulse",
  bad: "bg-destructive",
} as const;

export function StatusDot({ tone }: { tone: keyof typeof DOT_TONE }) {
  return <span className={cn("size-[7px] shrink-0 rounded-full", DOT_TONE[tone])} aria-hidden="true" />;
}

export function StatusPill({ status }: { status: DocumentInfo["status"] }) {
  const tone = status === "ready" ? "ok" : status === "failed" ? "bad" : "busy";
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-muted-foreground">
      <StatusDot tone={tone} />
      {STATUS_TEXT[status]}
    </span>
  );
}

export const PIPELINE_STEPS: { key: DocumentInfo["status"] | "uploading"; label: string }[] = [
  { key: "uploading", label: "Upload" },
  { key: "extracting", label: "Extract text" },
  { key: "chunking", label: "Split into passages" },
  { key: "embedding", label: "Embed" },
  { key: "indexing", label: "Index" },
  { key: "ready", label: "Ready" },
];

export function Similarity({ value }: { value: number }) {
  const width = Math.max(0, Math.min(1, value)) * 100;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
      title="Cosine similarity between the question and this passage. A retrieval signal, not proof that the passage supports the answer."
    >
      <span className="h-1 w-10 overflow-hidden rounded-full bg-secondary" aria-hidden="true">
        <span className="block h-full bg-muted-foreground" style={{ width: `${width}%` }} />
      </span>
      <span className="tabular-nums">{value.toFixed(2)} similarity</span>
    </span>
  );
}
