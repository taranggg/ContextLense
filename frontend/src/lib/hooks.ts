import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { DocumentInfo, Readiness } from "../api/types";

export const PROCESSING: DocumentInfo["status"][] = ["queued", "extracting", "chunking", "embedding", "indexing"];

export function isProcessing(doc: DocumentInfo): boolean {
  return PROCESSING.includes(doc.status);
}

/** Polls /api/ready: quickly while something is loading, slowly once settled. */
export function useReadiness() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let timer: number | undefined;
    let cancelled = false;
    const tick = async () => {
      let delay = 15000;
      try {
        const r = await api.ready();
        if (cancelled) return;
        setReadiness(r);
        setError(null);
        if (r.llm.status === "loading" || r.embedding.status === "loading") delay = 2000;
      } catch (err) {
        if (cancelled) return;
        setError(err as ApiError);
        delay = 4000;
      }
      timer = window.setTimeout(tick, delay);
    };
    tick();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  return { readiness, error };
}

/** Document list, polled while any document is still processing. */
export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentInfo[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    window.clearTimeout(timer.current);
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
      setError(null);
      if (docs.some(isProcessing)) timer.current = window.setTimeout(refresh, 1000);
    } catch (err) {
      setError(err as ApiError);
      timer.current = window.setTimeout(refresh, 4000);
    }
  }, []);

  useEffect(() => {
    refresh();
    return () => window.clearTimeout(timer.current);
  }, [refresh]);

  return { documents, error, refresh, setDocuments };
}

/** Like useState, persisted to localStorage (per-browser convenience only). */
export function useStoredState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage unavailable or full */
    }
  }, [key, value]);
  return [value, setValue] as const;
}

export function llmUsable(readiness: Readiness | null): boolean {
  if (!readiness) return false;
  return ["ready", "loading", "not_loaded"].includes(readiness.llm.status);
}
