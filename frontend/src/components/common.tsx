import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import type { ReactNode } from "react";
import type { DocumentInfo } from "../api/types";

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
    <div className={`notice ${tone}`} role={tone === "error" ? "alert" : "status"}>
      <Icon size={16} aria-hidden="true" />
      <div>
        {children}
        {actions && <div className="notice-actions">{actions}</div>}
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

export function StatusPill({ status }: { status: DocumentInfo["status"] }) {
  const tone = status === "ready" ? "ok" : status === "failed" ? "bad" : "busy";
  return (
    <span className="status-pill">
      <span className={`dot ${tone}`} aria-hidden="true" />
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
    <span className="sim" title="Cosine similarity between the question and this passage. A retrieval signal, not proof that the passage supports the answer.">
      <span className="sim-bar" aria-hidden="true">
        <span style={{ width: `${width}%` }} />
      </span>
      <span className="tabular">{value.toFixed(2)} similarity</span>
    </span>
  );
}
