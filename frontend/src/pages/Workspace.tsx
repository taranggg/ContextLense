import { ArrowUp, FileText, History, Library, PanelLeft, Square, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError, streamChat } from "../api/client";
import type { ConversationSummary, DocumentInfo, SavedTurn } from "../api/types";
import { Inspector, type InspectorTab } from "../components/Inspector";
import { Turn, type ChatTurn } from "../components/Turn";
import { Notice, StatusPill } from "../components/common";
import { formatDate, plural } from "../lib/format";
import { isProcessing, llmUsable, useConversations, useDocuments, useStoredState } from "../lib/hooks";
import { useReady } from "../lib/readiness";

const SUGGESTIONS = ["What is this document about?", "What are the key requirements or deadlines?"];

function fromSavedTurn(t: SavedTurn): ChatTurn {
  return { id: t.id, question: t.question, k: t.k, status: t.status, partial: t.response?.answer ?? "", response: t.response ?? undefined };
}

function Chat({ docs, sidebarOpen, onToggleSidebar, onConversationChange }: {
  docs: DocumentInfo[];
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onConversationChange: () => void;
}) {
  const { readiness } = useReady();
  const documentIds = useMemo(() => docs.map((d) => d.id), [docs]);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [turnsLoaded, setTurnsLoaded] = useState(false);
  const [draft, setDraft] = useState("");
  const [k, setK] = useStoredState<number>("contextlens:k", readiness?.limits.default_top_k ?? 5);
  const [inspector, setInspector] = useState<{ turnId: string | null; focus: string | null; tab: InspectorTab } | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load this document selection's saved conversation (chat memory) once, on mount.
  useEffect(() => {
    let cancelled = false;
    api
      .getConversation(documentIds)
      .then((conv) => !cancelled && setTurns(conv.turns.map(fromSavedTurn)))
      .catch(() => !cancelled && setTurns([]))
      .finally(() => !cancelled && setTurnsLoaded(true));
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, []);

  const busy = turns.some((t) => t.status === "retrieving" || t.status === "generating");
  const modelOk = llmUsable(readiness);
  const canSend = !busy && modelOk && draft.trim().length > 0;

  const update = useCallback(
    (id: string, patch: Partial<ChatTurn> | ((t: ChatTurn) => Partial<ChatTurn>)) =>
      setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, ...(typeof patch === "function" ? patch(t) : patch) } : t))),
    [setTurns],
  );

  // Keep the newest content in view while the user is near the bottom.
  const lastTurn = turns[turns.length - 1];
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 240) el.scrollTop = el.scrollHeight;
  }, [lastTurn?.partial, lastTurn?.status, turns.length]);

  const ask = async (question: string) => {
    const id = crypto.randomUUID();
    const controller = new AbortController();
    abortRef.current = controller;
    setTurns((ts) => [...ts, { id, question, k, status: "retrieving", partial: "" }]);
    requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    });
    try {
      const response = await streamChat(question, documentIds, k, controller.signal, {
        onRetrieved: (retrieved) => update(id, { status: "generating", retrieved }),
        onToken: (text) => update(id, (t) => ({ partial: t.partial + text })),
      });
      update(id, { status: response.cancelled ? "cancelled" : "done", response, partial: response.answer });
      onConversationChange();
    } catch (err) {
      if ((err as Error).name === "AbortError") update(id, { status: "cancelled" });
      else {
        const e = err as ApiError;
        update(id, { status: "error", error: { code: e.code ?? "error", message: e.message } });
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  };

  const send = () => {
    if (!canSend) return;
    const q = draft.trim();
    setDraft("");
    ask(q);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  };

  // Auto-grow the textarea.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [draft]);

  const inspectedTurn = inspector?.turnId ? turns.find((t) => t.id === inspector.turnId) : undefined;
  const title = docs.length === 1 ? docs[0].filename : `${docs.length} documents`;
  const totalPages = docs.reduce((n, d) => n + (d.page_count ?? 0), 0);

  return (
    <section className="chat" aria-label="Conversation">
      <div className="chat-bar">
        <button
          type="button"
          className="icon-btn"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Hide document list" : "Show document list"}
          aria-expanded={sidebarOpen}
        >
          <PanelLeft size={18} />
        </button>
        <div className="chat-bar-title">
          <strong title={docs.map((d) => d.filename).join(", ")}>{title}</strong>
          <span>
            {plural(totalPages, "page")} · {plural(docs.reduce((n, d) => n + (d.chunk_count ?? 0), 0), "passage")} indexed
          </span>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setInspector({ turnId: null, focus: null, tab: "document" })}>
          <Library size={15} aria-hidden="true" /> Passages
        </button>
        {turns.length > 0 && (
          <button
            type="button"
            className="icon-btn"
            disabled={busy}
            onClick={() => {
              setTurns([]);
              api.deleteConversation(documentIds).then(onConversationChange).catch(() => {});
            }}
            aria-label="Clear conversation"
            title="Clear conversation"
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        {!turnsLoaded ? (
          <div className="thinking" style={{ justifyContent: "center", marginTop: 40 }}>
            <span className="spinner" aria-hidden="true" /> Loading conversation…
          </div>
        ) : turns.length === 0 ? (
          <div className="chat-empty">
            <h2>Ask about {docs.length === 1 ? "this document" : "these documents"}.</h2>
            <p>Answers use only the text of {docs.length === 1 ? docs[0].filename : "the selected documents"}, with the passages they come from.</p>
            {modelOk && (
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="suggestion" onClick={() => ask(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="thread">
            {turns.map((turn) => (
              <Turn
                key={turn.id}
                turn={turn}
                onInspect={(focus) => setInspector({ turnId: turn.id, focus, tab: "passages" })}
                onRetry={() => {
                  setTurns((ts) => ts.filter((t) => t.id !== turn.id));
                  ask(turn.question);
                }}
              />
            ))}
          </div>
        )}
      </div>

      <div className="composer-wrap">
        {readiness && !modelOk && (
          <div style={{ maxWidth: 740, margin: "0 auto 10px" }}>
            <Notice tone="error">
              The local model is unavailable, so questions can't be answered right now. {readiness.llm.detail}
            </Notice>
          </div>
        )}
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <label htmlFor="question" className="visually-hidden">
            Ask a question
          </label>
          <textarea
            id="question"
            ref={textareaRef}
            rows={1}
            value={draft}
            placeholder={modelOk ? "Ask a question…" : "Waiting for the local model…"}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={readiness?.limits.max_question_chars ?? 2000}
          />
          {busy ? (
            <button type="button" className="send-btn" onClick={() => abortRef.current?.abort()} aria-label="Stop generating">
              <Square size={14} fill="currentColor" />
            </button>
          ) : (
            <button type="submit" className="send-btn" disabled={!canSend} aria-label="Send question">
              <ArrowUp size={18} />
            </button>
          )}
        </form>
        <div className="composer-foot">
          <span>Enter to send · Shift+Enter for a new line</span>
          <label className="depth-select">
            Passages per answer
            <select value={k} onChange={(e) => setK(Number(e.target.value))} disabled={busy}>
              {[1, 3, 5, 10].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {inspector && (
        <Inspector
          tab={inspector.tab}
          onTab={(tab) => setInspector({ ...inspector, tab })}
          onClose={() => setInspector(null)}
          retrieved={inspectedTurn ? inspectedTurn.response?.retrieved ?? inspectedTurn.retrieved ?? null : null}
          response={inspectedTurn?.response ?? null}
          focus={inspector.focus}
          documents={docs}
        />
      )}
    </section>
  );
}

const sameDocs = (a: string[], b: string[]) => [...a].sort().join(",") === [...b].sort().join(",");

function openConversation(navigate: ReturnType<typeof useNavigate>, ids: string[]) {
  const [first, ...rest] = ids;
  navigate(`/documents/${first}${rest.length ? `?with=${rest.join(",")}` : ""}`);
}

function HistoryList({ conversations, activeIds, navigate, onDelete }: {
  conversations: ConversationSummary[] | null;
  activeIds: string[];
  navigate: ReturnType<typeof useNavigate>;
  onDelete: (ids: string[]) => void;
}) {
  if (!conversations) return <p className="empty" style={{ padding: "8px 8px" }}>Loading…</p>;
  if (conversations.length === 0) return <p className="empty" style={{ padding: "8px 8px" }}>No conversations yet.</p>;
  return (
    <>
      {conversations.map((conv) => {
        const key = conv.document_ids.join(",");
        const active = sameDocs(conv.document_ids, activeIds);
        return (
          <div key={key} className={`sidebar-doc history-row${active ? " active" : ""}`}>
            <button type="button" className="history-open" onClick={() => openConversation(navigate, conv.document_ids)}>
              <span className="name">{conv.title}</span>
              <span className="meta" style={{ display: "block" }}>
                {conv.document_names.join(", ")} · {plural(conv.turn_count, "message")} · {formatDate(conv.updated_at)}
              </span>
            </button>
            <button
              type="button"
              className="icon-btn"
              aria-label="Delete conversation"
              title="Delete conversation"
              onClick={() => onDelete(conv.document_ids)}
            >
              <Trash2 size={14} />
            </button>
          </div>
        );
      })}
    </>
  );
}

export function Workspace() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { documents, error } = useDocuments();
  const { conversations, refresh: refreshConversations } = useConversations();
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 860);
  const [sidebarTab, setSidebarTab] = useStoredState<"documents" | "history">("contextlens:sidebarTab", "documents");
  const [reloadToken, setReloadToken] = useState(0);

  const selectedIds = useMemo(() => {
    const extra = (params.get("with") ?? "").split(",").filter(Boolean);
    return [id, ...extra.filter((x) => x !== id)];
  }, [id, params]);

  const ready = (documents ?? []).filter((d) => d.status === "ready");
  const selected = selectedIds.map((sid) => documents?.find((d) => d.id === sid)).filter(Boolean) as DocumentInfo[];
  const primary = documents?.find((d) => d.id === id);

  const setSelection = (ids: string[]) => {
    if (!ids.length) return;
    const [first, ...rest] = ids;
    navigate(`/documents/${first}${rest.length ? `?with=${rest.join(",")}` : ""}`, { replace: true });
  };

  const deleteConversation = async (ids: string[]) => {
    await api.deleteConversation(ids);
    refreshConversations();
    if (sameDocs(ids, selectedIds)) setReloadToken((n) => n + 1);
  };

  if (error && !documents) {
    return (
      <main className="page page-narrow">
        <Notice tone="error">{error.message}</Notice>
      </main>
    );
  }
  if (!documents) return <main className="page page-narrow"><p className="empty">Loading…</p></main>;
  if (!primary) {
    return (
      <main className="page page-narrow">
        <Notice tone="error" actions={<Link to="/" className="btn btn-secondary btn-sm">Back to documents</Link>}>
          This document doesn't exist. It may have been deleted.
        </Notice>
      </main>
    );
  }
  if (primary.status !== "ready") {
    return (
      <main className="page page-narrow">
        <h1 style={{ fontSize: 28 }}>{primary.filename}</h1>
        <div style={{ marginTop: 16 }}>
          {isProcessing(primary) ? (
            <div className="thinking">
              <span className="spinner" aria-hidden="true" /> <StatusPill status={primary.status} />
            </div>
          ) : (
            <Notice tone="error" actions={<Link to="/" className="btn btn-secondary btn-sm">Back to documents</Link>}>
              {primary.error_message ?? "This document could not be processed."}
            </Notice>
          )}
        </div>
      </main>
    );
  }

  const readySelected = selected.filter((d) => d.status === "ready");

  return (
    <div className={`workspace${sidebarOpen ? "" : " sidebar-collapsed"}`}>
      <aside className="sidebar" aria-label="Documents and conversation history" aria-hidden={!sidebarOpen}>
        <div className="sidebar-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={sidebarTab === "documents"}
            className={`sidebar-tab${sidebarTab === "documents" ? " active" : ""}`}
            tabIndex={sidebarOpen ? 0 : -1}
            onClick={() => setSidebarTab("documents")}
          >
            <FileText size={14} aria-hidden="true" /> Documents
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={sidebarTab === "history"}
            className={`sidebar-tab${sidebarTab === "history" ? " active" : ""}`}
            tabIndex={sidebarOpen ? 0 : -1}
            onClick={() => setSidebarTab("history")}
          >
            <History size={14} aria-hidden="true" /> History
          </button>
        </div>

        {sidebarTab === "documents" ? (
          <>
            {ready.map((doc) => {
              const checked = selectedIds.includes(doc.id);
              return (
                <label key={doc.id} className="sidebar-doc">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={checked && selectedIds.length === 1}
                    tabIndex={sidebarOpen ? 0 : -1}
                    onChange={() =>
                      setSelection(checked ? selectedIds.filter((x) => x !== doc.id) : [...selectedIds, doc.id])
                    }
                  />
                  <span>
                    <span className="name">{doc.filename}</span>
                    <span className="meta" style={{ display: "block" }}>
                      {plural(doc.page_count ?? 0, "page")}
                      {doc.is_sample && " · sample"}
                    </span>
                  </span>
                </label>
              );
            })}
            <div className="sidebar-foot">
              <Link to="/" className="small" tabIndex={sidebarOpen ? 0 : -1}>
                Upload another PDF
              </Link>
            </div>
          </>
        ) : (
          <HistoryList conversations={conversations} activeIds={selectedIds} navigate={navigate} onDelete={deleteConversation} />
        )}
      </aside>
      <Chat
        key={`${readySelected.map((d) => d.id).sort().join(",")}:${reloadToken}`}
        docs={readySelected}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((o) => !o)}
        onConversationChange={refreshConversations}
      />
    </div>
  );
}
