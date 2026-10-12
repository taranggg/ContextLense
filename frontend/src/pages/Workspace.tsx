import { FileText, History, Library, PanelLeft, Send, Square, Trash2 } from "lucide-react";
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
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

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
    <section className="relative flex min-h-0 min-w-0 flex-col" aria-label="Conversation">
      <div className="flex min-h-[52px] items-center gap-2 overflow-x-hidden border-b border-border px-4 py-2.5">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Hide document list" : "Show document list"}
          aria-expanded={sidebarOpen}
        >
          <PanelLeft size={18} />
        </Button>
        <div className="min-w-0 flex-1">
          <strong
            title={docs.map((d) => d.filename).join(", ")}
            className="line-clamp-2 block overflow-hidden text-sm font-semibold leading-tight break-words"
          >
            {title}
          </strong>
          <span className="text-xs text-muted-foreground">
            {plural(totalPages, "page")} · {plural(docs.reduce((n, d) => n + (d.chunk_count ?? 0), 0), "passage")} indexed
          </span>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setInspector({ turnId: null, focus: null, tab: "document" })}>
          <Library size={15} aria-hidden="true" /> Passages
        </Button>
        {turns.length > 0 && (
          <Button
            variant="ghost"
            size="icon"
            disabled={busy}
            onClick={() => {
              setTurns([]);
              api.deleteConversation(documentIds).then(onConversationChange).catch(() => {});
            }}
            aria-label="Clear conversation"
            title="Clear conversation"
          >
            <Trash2 size={16} />
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto scroll-smooth" ref={scrollRef}>
        {!turnsLoaded ? (
          <div className="mt-10 flex items-center justify-center gap-2.5 text-[15px] text-muted-foreground">
            <span className="size-3.5 shrink-0 animate-spin rounded-full border-2 border-secondary border-t-foreground/60" aria-hidden="true" /> Loading
            conversation…
          </div>
        ) : turns.length === 0 ? (
          <div className="mx-auto mt-[12vh] max-w-[560px] px-6 text-center">
            <h2 className="text-[28px] tracking-[-0.025em]">Ask about {docs.length === 1 ? "this document" : "these documents"}.</h2>
            <p className="mt-2.5 break-words text-muted-foreground">
              Answers use only the text of {docs.length === 1 ? docs[0].filename : "the selected documents"}, with the passages they come from.
            </p>
            {modelOk && (
              <div className="mt-7 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="rounded-xl border border-input bg-card px-3.5 py-1.5 text-sm text-foreground/80 transition-colors hover:border-foreground/30 hover:text-foreground"
                    onClick={() => ask(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="mx-auto max-w-[740px] px-6 pb-6 pt-8">
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

      <div className="bg-gradient-to-t from-background to-transparent px-6 pb-5 pt-3">
        {readiness && !modelOk && (
          <div className="mx-auto mb-2.5 max-w-[740px]">
            <Notice tone="error">
              The local model is unavailable, so questions can't be answered right now. {readiness.llm.detail}
            </Notice>
          </div>
        )}
        <form
          className="mx-auto flex max-w-[740px] items-end gap-2 rounded-[22px] border border-input bg-card py-2 pl-4.5 pr-2 shadow-xs transition-colors focus-within:border-foreground/30"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <label htmlFor="question" className="sr-only">
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
            className="max-h-[200px] flex-1 resize-none border-none bg-transparent py-1.5 leading-snug outline-none"
          />
          {busy ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              aria-label="Stop generating"
              className="flex size-9 shrink-0 items-center justify-center rounded-full bg-foreground text-background transition-colors"
            >
              <Square size={14} fill="currentColor" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Send question"
              className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors disabled:bg-muted-foreground/40"
            >
              <Send size={16} />
            </button>
          )}
        </form>
        <div className="mx-auto mt-2 flex max-w-[740px] justify-between gap-3 text-xs text-muted-foreground">
          <span>Enter to send · Shift+Enter for a new line</span>
          <label className="inline-flex items-center gap-1.5">
            Passages per answer
            <Select value={k} onChange={(e) => setK(Number(e.target.value))} disabled={busy} className="h-6 px-1.5 text-xs">
              {[1, 3, 5, 10].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </Select>
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
  if (!conversations) return <p className="px-2 py-2 text-center text-[15px] text-muted-foreground">Loading…</p>;
  if (conversations.length === 0) return <p className="px-2 py-2 text-center text-[15px] text-muted-foreground">No conversations yet.</p>;
  return (
    <>
      {conversations.map((conv) => {
        const key = conv.document_ids.join(",");
        const active = sameDocs(conv.document_ids, activeIds);
        return (
          <div key={key} className={cn("group flex items-center gap-2.5 rounded-lg p-2 pr-1", active && "bg-secondary")}>
            <button type="button" className="min-w-0 flex-1 bg-none p-0 text-left text-sm" onClick={() => openConversation(navigate, conv.document_ids)}>
              <span className="block break-words leading-snug">{conv.title}</span>
              <span className="block break-words text-xs text-muted-foreground">
                {conv.document_names.join(", ")} · {plural(conv.turn_count, "message")} · {formatDate(conv.updated_at)}
              </span>
            </button>
            <Button
              variant="ghost"
              size="icon"
              className="size-[26px] shrink-0 opacity-0 transition-opacity group-hover:opacity-100 hover:opacity-100"
              aria-label="Delete conversation"
              title="Delete conversation"
              onClick={() => onDelete(conv.document_ids)}
            >
              <Trash2 size={14} />
            </Button>
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
      <main className="mx-auto max-w-[760px] px-6 pb-24 pt-[72px]">
        <Notice tone="error">{error.message}</Notice>
      </main>
    );
  }
  if (!documents)
    return (
      <main className="mx-auto max-w-[760px] px-6 pb-24 pt-[72px]">
        <p className="py-10 text-center text-[15px] text-muted-foreground">Loading…</p>
      </main>
    );
  if (!primary) {
    return (
      <main className="mx-auto max-w-[760px] px-6 pb-24 pt-[72px]">
        <Notice tone="error" actions={<Button asChild variant="secondary" size="sm"><Link to="/">Back to documents</Link></Button>}>
          This document doesn't exist. It may have been deleted.
        </Notice>
      </main>
    );
  }
  if (primary.status !== "ready") {
    return (
      <main className="mx-auto max-w-[760px] px-6 pb-24 pt-[72px]">
        <h1 className="break-words text-[28px] font-semibold">{primary.filename}</h1>
        <div className="mt-4">
          {isProcessing(primary) ? (
            <div className="flex items-center gap-2.5 text-[15px] text-muted-foreground">
              <span className="size-3.5 shrink-0 animate-spin rounded-full border-2 border-secondary border-t-foreground/60" aria-hidden="true" />{" "}
              <StatusPill status={primary.status} />
            </div>
          ) : (
            <Notice tone="error" actions={<Button asChild variant="secondary" size="sm"><Link to="/">Back to documents</Link></Button>}>
              {primary.error_message ?? "This document could not be processed."}
            </Notice>
          )}
        </div>
      </main>
    );
  }

  const readySelected = selected.filter((d) => d.status === "ready");

  return (
    <div
      className={cn(
        "grid h-[calc(100dvh-56px)] grid-cols-[264px_minmax(0,1fr)] max-[860px]:grid-cols-[minmax(0,1fr)]",
        !sidebarOpen && "grid-cols-[0_minmax(0,1fr)] max-[860px]:grid-cols-[minmax(0,1fr)]",
      )}
    >
      <aside
        aria-label="Documents and conversation history"
        aria-hidden={!sidebarOpen}
        className={cn(
          "overflow-y-auto border-r border-border bg-background p-3",
          !sidebarOpen && "invisible border-none p-0 max-[860px]:invisible",
          "max-[860px]:fixed max-[860px]:inset-y-0 max-[860px]:left-0 max-[860px]:top-14 max-[860px]:z-20 max-[860px]:w-[280px] max-[860px]:shadow-lg",
        )}
      >
        <div className="mb-3.5 mx-1 flex gap-1 rounded-md bg-muted p-0.5" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={sidebarTab === "documents"}
            tabIndex={sidebarOpen ? 0 : -1}
            className={cn(
              "flex h-[30px] flex-1 items-center justify-center gap-1.5 rounded-sm text-[12.5px] font-medium text-muted-foreground transition-colors",
              sidebarTab === "documents" && "bg-card text-foreground shadow-xs",
            )}
            onClick={() => setSidebarTab("documents")}
          >
            <FileText size={14} aria-hidden="true" /> Documents
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={sidebarTab === "history"}
            tabIndex={sidebarOpen ? 0 : -1}
            className={cn(
              "flex h-[30px] flex-1 items-center justify-center gap-1.5 rounded-sm text-[12.5px] font-medium text-muted-foreground transition-colors",
              sidebarTab === "history" && "bg-card text-foreground shadow-xs",
            )}
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
                <label key={doc.id} className="flex cursor-pointer items-start gap-2.5 rounded-md p-2 text-sm hover:bg-secondary">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={checked && selectedIds.length === 1}
                    tabIndex={sidebarOpen ? 0 : -1}
                    className="mt-1 shrink-0 accent-primary"
                    onChange={() =>
                      setSelection(checked ? selectedIds.filter((x) => x !== doc.id) : [...selectedIds, doc.id])
                    }
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block break-words leading-snug">{doc.filename}</span>
                    <span className="block break-words text-xs text-muted-foreground">
                      {plural(doc.page_count ?? 0, "page")}
                      {doc.is_sample && " · sample"}
                    </span>
                  </span>
                </label>
              );
            })}
            <div className="mt-4 px-2">
              <Link to="/" className="text-sm" tabIndex={sidebarOpen ? 0 : -1}>
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
