import type {
  BatchUploadResult,
  ChatResponse,
  ChunkPage,
  Comparison,
  ConditionResult,
  Conversation,
  ConversationSummary,
  DocumentInfo,
  Readiness,
  ResearchResults,
  RetrievedChunk,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

const NETWORK_MESSAGE = "Can't reach the ContextLens backend. Make sure it is running on " + API_BASE + ".";

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    if (body?.error?.message) return new ApiError(res.status, body.error.code, body.error.message);
  } catch {
    /* fall through */
  }
  return new ApiError(res.status, "http_error", `The server responded with ${res.status}.`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, init);
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "network", NETWORK_MESSAGE);
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown, signal?: AbortSignal): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
  signal,
});

export const api = {
  ready: () => request<Readiness>("/api/ready"),
  listDocuments: () => request<{ documents: DocumentInfo[] }>("/api/documents").then((r) => r.documents),
  getDocument: (id: string) => request<DocumentInfo>(`/api/documents/${id}`),
  deleteDocument: (id: string) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  reprocessDocument: (id: string) => request<DocumentInfo>(`/api/documents/${id}/reprocess`, { method: "POST" }),
  chunks: (id: string, offset = 0, limit = 20) =>
    request<ChunkPage>(`/api/documents/${id}/chunks?offset=${offset}&limit=${limit}`),
  researchResults: () => request<ResearchResults>("/api/research/results"),
  comparison: (id: string) => request<Comparison>(`/api/research/comparisons/${id}`),
  benchmarkRun: (id: string) => request<{ summary: unknown; runs: unknown[] }>(`/api/research/benchmark/${id}`),
  listConversations: () => request<{ conversations: ConversationSummary[] }>("/api/conversations").then((r) => r.conversations),
  getConversation: (documentIds: string[]) => request<Conversation>(`/api/conversations/${documentIds.join(",")}`),
  deleteConversation: (documentIds: string[]) =>
    request<void>(`/api/conversations/${documentIds.join(",")}`, { method: "DELETE" }),
};

/** Upload several PDFs in one request, with progress (fetch has no upload progress events). */
export function uploadDocuments(
  files: File[],
  onProgress: (fraction: number) => void,
): { promise: Promise<BatchUploadResult>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<BatchUploadResult>((resolve, reject) => {
    xhr.open("POST", API_BASE + "/api/documents/batch");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let body: any = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as BatchUploadResult);
      else
        reject(
          new ApiError(
            xhr.status,
            body?.error?.code ?? "http_error",
            body?.error?.message ?? `Upload failed (${xhr.status}).`,
          ),
        );
    };
    xhr.onerror = () => reject(new ApiError(0, "network", NETWORK_MESSAGE));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    const form = new FormData();
    for (const file of files) form.append("files", file);
    xhr.send(form);
  });
  return { promise, abort: () => xhr.abort() };
}

/** POST a JSON body and read a server-sent event stream. */
async function streamEvents(
  path: string,
  body: unknown,
  signal: AbortSignal,
  onEvent: (event: string, data: any) => void,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, json(body, signal));
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "network", NETWORK_MESSAGE);
  }
  if (!res.ok || !res.body) throw await toApiError(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of raw.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data.push(line.slice(6));
      }
      const payload = data.length ? JSON.parse(data.join("\n")) : null;
      if (event === "error") throw new ApiError(payload?.status ?? 500, payload?.code ?? "error", payload?.message ?? "Request failed.");
      onEvent(event, payload);
    }
  }
}

export interface ChatHandlers {
  onRetrieved?: (chunks: RetrievedChunk[]) => void;
  onToken?: (text: string) => void;
}

export async function streamChat(
  question: string,
  documentIds: string[],
  k: number | undefined,
  signal: AbortSignal,
  handlers: ChatHandlers,
): Promise<ChatResponse> {
  let final: ChatResponse | null = null;
  await streamEvents("/api/chat/stream", { question, document_ids: documentIds, k }, signal, (event, data) => {
    if (event === "retrieval") handlers.onRetrieved?.(data.retrieved);
    else if (event === "token") handlers.onToken?.(data.text);
    else if (event === "done") final = data;
  });
  if (!final) throw new ApiError(500, "incomplete", "The answer stream ended unexpectedly.");
  return final;
}

export async function streamCompare(
  body: { question: string; document_ids: string[]; k_values?: number[]; include_no_rag?: boolean },
  signal: AbortSignal,
  handlers: { onStart?: (conditions: string[]) => void; onCondition?: (c: ConditionResult) => void },
): Promise<Comparison> {
  let final: Comparison | null = null;
  await streamEvents("/api/research/compare/stream", body, signal, (event, data) => {
    if (event === "start") handlers.onStart?.(data.conditions);
    else if (event === "condition") handlers.onCondition?.(data);
    else if (event === "done") final = data;
  });
  if (!final) throw new ApiError(500, "incomplete", "The comparison stream ended unexpectedly.");
  return final;
}
