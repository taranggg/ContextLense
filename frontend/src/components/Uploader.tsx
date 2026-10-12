import { Check, FileText, FileUp, X } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, uploadDocument } from "../api/client";
import type { DocumentInfo } from "../api/types";
import { formatBytes } from "../lib/format";
import { Notice, PIPELINE_STEPS } from "./common";

type State =
  | { phase: "idle" }
  | { phase: "uploading"; file: File; progress: number; abort: () => void }
  | { phase: "processing"; file: File; doc: DocumentInfo }
  | { phase: "error"; file?: File; message: string; doc?: DocumentInfo };

export function Uploader({ maxMb, onChange }: { maxMb: number; onChange: () => void }) {
  const [state, setState] = useState<State>({ phase: "idle" });
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Poll the document while it is being processed.
  useEffect(() => {
    if (state.phase !== "processing") return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const doc = await api.getDocument(state.doc.id);
        if (cancelled) return;
        if (doc.status === "ready") {
          onChange();
          navigate(`/documents/${doc.id}`);
        } else if (doc.status === "failed") {
          onChange();
          setState({ phase: "error", file: state.file, doc, message: doc.error_message ?? "Processing failed." });
        } else {
          setState({ ...state, doc });
        }
      } catch (err) {
        if (!cancelled) setState({ phase: "error", file: state.file, message: (err as ApiError).message });
      }
    }, 700);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [state, navigate, onChange]);

  const start = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type !== "application/pdf")) {
      setState({ phase: "error", file, message: "Only PDF files are supported." });
      return;
    }
    if (file.size > maxMb * 1024 * 1024) {
      setState({ phase: "error", file, message: `This file is ${formatBytes(file.size)}. The limit is ${maxMb} MB.` });
      return;
    }
    const { promise, abort } = uploadDocument(file, (progress) =>
      setState((s) => (s.phase === "uploading" ? { ...s, progress } : s)),
    );
    setState({ phase: "uploading", file, progress: 0, abort });
    promise
      .then((doc) => {
        onChange();
        setState({ phase: "processing", file, doc });
      })
      .catch((err) => {
        if ((err as Error).name === "AbortError") setState({ phase: "idle" });
        else setState({ phase: "error", file, message: (err as ApiError).message });
      });
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (state.phase === "uploading" || state.phase === "processing") return;
    const file = e.dataTransfer.files[0];
    if (file) start(file);
  };

  const busy = state.phase === "uploading" || state.phase === "processing";
  const currentKey = state.phase === "uploading" ? "uploading" : state.phase === "processing" ? state.doc.status : null;
  const currentIndex = PIPELINE_STEPS.findIndex((s) => s.key === (currentKey === "queued" ? "extracting" : currentKey));

  return (
    <div
      className={`dropzone${dragging ? " dragging" : ""}`}
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
        className="visually-hidden"
        tabIndex={-1}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) start(file);
        }}
      />

      {busy ? (
        <div className="upload-card" aria-live="polite">
          <div className="upload-name">
            <FileText size={18} aria-hidden="true" />
            <span>{state.file.name}</span>
            <span className="muted small">{formatBytes(state.file.size)}</span>
            <span className="header-spacer" />
            {state.phase === "uploading" && (
              <button type="button" className="icon-btn" onClick={state.abort} aria-label="Cancel upload">
                <X size={16} />
              </button>
            )}
          </div>
          <div className={`progress${state.phase === "processing" ? " indeterminate" : ""}`}>
            <span style={{ width: state.phase === "uploading" ? `${Math.round(state.progress * 100)}%` : undefined }} />
          </div>
          <ol className="steps">
            {PIPELINE_STEPS.map((step, i) => (
              <li key={step.key} className={i < currentIndex ? "done" : i === currentIndex ? "current" : ""}>
                {i < currentIndex && <Check size={13} aria-hidden="true" />}
                {step.label}
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <>
          <FileUp size={32} strokeWidth={1.5} className="dropzone-icon" aria-hidden="true" />
          <p className="dropzone-title">Drop a PDF here</p>
          <button type="button" className="btn btn-secondary" onClick={() => input.current?.click()}>
            Browse files
          </button>
          <p className="dropzone-hint">PDF with selectable text · up to {maxMb} MB · scanned pages are not supported (no OCR)</p>
          {state.phase === "error" && (
            <div className="upload-card" style={{ marginTop: 12 }}>
              <Notice tone="error">
                {state.file && <strong>{state.file.name}: </strong>}
                {state.message}
              </Notice>
            </div>
          )}
        </>
      )}
    </div>
  );
}
