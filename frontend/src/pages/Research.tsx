import { ChevronRight, CircleHelp, Play, Search, Square, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, streamCompare } from "../api/client";
import type {
  BenchmarkSummary,
  Comparison,
  ComparisonSummary,
  ConditionAggregate,
  ConditionResult,
  DocumentInfo,
} from "../api/types";
import { AnswerText } from "../components/AnswerText";
import { BarChart } from "../components/BarChart";
import { Notice, Similarity } from "../components/common";
import { formatDate, formatMs, formatPages, num, pct } from "../lib/format";
import { llmUsable, useDocuments } from "../lib/hooks";
import { useReady } from "../lib/readiness";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const CONDITION_LABEL: Record<string, string> = {
  no_rag: "No retrieval",
  "k=1": "Top-1",
  "k=3": "Top-3",
  "k=5": "Top-5",
  "k=10": "Top-10",
  k1: "Top-1",
  k3: "Top-3",
  k5: "Top-5",
  k10: "Top-10",
  gold: "Gold page",
};
const label = (c: string) => CONDITION_LABEL[c] ?? c;

// ------------------------------------------------------------------ live comparison

function Disclosure({ summary, children }: { summary: ReactNode; children: ReactNode }) {
  return (
    <details className="mt-4 group">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-[13px] font-medium text-foreground/80 marker:content-none [&::-webkit-details-marker]:hidden">
        <ChevronRight size={14} className="transition-transform group-open:rotate-90" /> {summary}
      </summary>
      {children}
    </details>
  );
}

function PassageItem({ c, showSimilarity = true }: { c: { chunk_id: string; source_label: string; document_name: string; pages: number[]; similarity: number; text: string }; showSimilarity?: boolean }) {
  return (
    <li className="list-none border-b border-border py-3 last:border-none">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px]">
        <span className="grid h-5 min-w-[26px] place-items-center rounded-md bg-accent px-1.5 text-[11px] font-semibold text-accent-foreground">
          {c.source_label}
        </span>
        <span className="break-words font-medium">{c.document_name}</span>
        <span className="text-muted-foreground">{formatPages(c.pages)}</span>
      </div>
      {showSimilarity && (
        <div className="mt-1">
          <Similarity value={c.similarity} />
        </div>
      )}
      <p className="mt-1.5 line-clamp-6 whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/80">{c.text}</p>
    </li>
  );
}

function ConditionCard({ result, pending }: { result?: ConditionResult; pending: string }) {
  if (!result) {
    return (
      <Card className="flex min-w-0 flex-col gap-3.5 p-4.5" aria-busy="true">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-[17px] font-semibold">{label(pending)}</h3>
        </div>
        <div className="flex min-h-20 items-center gap-2 text-[13px] text-muted-foreground">
          <span className="size-3.5 shrink-0 animate-spin rounded-full border-2 border-secondary border-t-foreground/60" aria-hidden="true" /> Waiting…
        </div>
      </Card>
    );
  }
  const m = result.metrics;
  const included = result.generation ? result.retrieved.slice(0, result.generation.sources_in_prompt) : result.retrieved;
  const valid = new Set(included.map((c) => c.source_label));
  const unsupported = m?.claim_checks.filter((c) => c.label === "unsupported") ?? [];
  return (
    <Card className="flex min-w-0 flex-col gap-3.5 p-4.5">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-[17px] font-semibold">{label(result.condition)}</h3>
        <span className="text-xs tabular-nums text-muted-foreground">{formatMs(result.latency?.total_ms)}</span>
      </div>
      {result.error ? (
        <Notice tone="error">{result.error}</Notice>
      ) : (
        <div className="text-sm leading-relaxed">
          <AnswerText text={result.answer ?? ""} validLabels={valid} />
        </div>
      )}
      {m && (
        <dl className="grid gap-1.5 border-t border-border pt-3 text-xs">
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Correctness</dt>
            <dd className="text-right text-muted-foreground">Not evaluated</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Abstained</dt>
            <dd className="text-right tabular-nums">{m.abstained ? "Yes" : "No"}</dd>
          </div>
          {result.condition !== "no_rag" && (
            <>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Citations matching a passage</dt>
                <dd className="text-right tabular-nums">{m.citation_count ? `${m.citation_count - m.invalid_citation_count} of ${m.citation_count}` : "none"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground" title="Lexical check: most content words and all numbers of the sentence appear in the supplied passages.">
                  Sentences found in passages*
                </dt>
                <dd className="text-right tabular-nums">{m.claims_total ? `${m.claims_lexically_supported} of ${m.claims_total}` : "—"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Prompt tokens</dt>
                <dd className="text-right tabular-nums">{result.generation?.prompt_tokens?.toLocaleString() ?? "—"}</dd>
              </div>
            </>
          )}
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Generation</dt>
            <dd className="text-right tabular-nums">{formatMs(result.latency?.generation_ms)}</dd>
          </div>
        </dl>
      )}
      {result.generation?.context_truncated && (
        <Notice tone="warn">Context trimmed: {result.generation.sources_in_prompt} of {result.retrieved.length} passages fit.</Notice>
      )}
      {unsupported.length > 0 && (
        <Disclosure summary={`Not found in passages (${unsupported.length})`}>
          <ul className="mt-2 grid list-none gap-1.5 p-0 text-[13px]">
            {unsupported.map((c) => (
              <li key={c.claim} className="flex gap-2 text-foreground/80">
                <CircleHelp size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                <span>
                  {c.claim}
                  {c.missing_numbers.length > 0 && <span className="text-muted-foreground"> — numbers not in passages: {c.missing_numbers.join(", ")}</span>}
                </span>
              </li>
            ))}
          </ul>
        </Disclosure>
      )}
      {result.retrieved.length > 0 && (
        <Disclosure summary={`Retrieved passages (${result.retrieved.length})`}>
          <ul className="m-0 mt-2 list-none p-0">
            {result.retrieved.map((c) => (
              <PassageItem key={c.chunk_id} c={c} />
            ))}
          </ul>
        </Disclosure>
      )}
    </Card>
  );
}

function LiveCompare({ documents, onSaved, loaded }: { documents: DocumentInfo[]; onSaved: () => void; loaded: Comparison | null }) {
  const { readiness } = useReady();
  const ready = documents.filter((d) => d.status === "ready");
  const [selected, setSelected] = useState<string[]>([]);
  const [docFilter, setDocFilter] = useState("");
  const [question, setQuestion] = useState("");
  const [includeNoRag, setIncludeNoRag] = useState(false);
  const [planned, setPlanned] = useState<string[]>([]);
  const [results, setResults] = useState<ConditionResult[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!selected.length && ready.length) setSelected([ready.find((d) => !d.is_sample)?.id ?? ready[0].id]);
  }, [ready, selected.length]);

  useEffect(() => {
    if (!loaded) return;
    setComparison(loaded);
    setQuestion(loaded.question);
    setResults(loaded.conditions);
    setPlanned(loaded.conditions.map((c) => c.condition));
    setError(null);
  }, [loaded]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const run = async () => {
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setError(null);
    setResults([]);
    setComparison(null);
    setPlanned([...(includeNoRag ? ["no_rag"] : []), ...(readiness?.limits.research_k_values ?? [1, 3, 5, 10]).map((k) => `k=${k}`)]);
    try {
      const done = await streamCompare(
        { question: question.trim(), document_ids: selected, include_no_rag: includeNoRag },
        controller.signal,
        {
          onStart: setPlanned,
          onCondition: (c) => setResults((rs) => [...rs, c]),
        },
      );
      setComparison(done);
      onSaved();
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as ApiError).message);
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  };

  const canRun = !running && question.trim().length > 0 && selected.length > 0 && llmUsable(readiness);

  const filteredReady = useMemo(() => {
    const q = docFilter.trim().toLowerCase();
    if (!q) return ready;
    return ready.filter((d) => d.filename.toLowerCase().includes(q));
  }, [ready, docFilter]);

  return (
    <section className="mt-[72px]" aria-labelledby="compare-title">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 id="compare-title" className="text-xl font-semibold">
          Compare retrieval depths
        </h2>
      </div>
      <Card className="p-6">
        <div>
          <div className="mb-2 flex items-baseline justify-between gap-3">
            <span className="text-[13px] font-medium" id="docs-label">
              Documents
            </span>
            <span className="text-[13px] text-muted-foreground">
              {selected.length} selected of {ready.length}
            </span>
          </div>
          {ready.length ? (
            <div className="overflow-hidden rounded-lg border border-input bg-card">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted px-3 py-2.5">
                <div className="flex min-w-[200px] flex-1 items-center gap-1.5 text-muted-foreground">
                  <Search size={14} aria-hidden="true" />
                  <input
                    type="text"
                    value={docFilter}
                    onChange={(e) => setDocFilter(e.target.value)}
                    placeholder={`Filter ${ready.length} document${ready.length === 1 ? "" : "s"}…`}
                    aria-label="Filter documents"
                    disabled={running}
                    className="min-w-0 flex-1 border-none bg-transparent text-[13px] text-foreground outline-none"
                  />
                  {docFilter && (
                    <button type="button" className="inline-flex p-0.5 text-muted-foreground hover:text-foreground" onClick={() => setDocFilter("")} aria-label="Clear filter">
                      <X size={13} aria-hidden="true" />
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-3 whitespace-nowrap text-[13px]">
                  <button
                    type="button"
                    className="bg-none p-0 text-primary hover:underline disabled:pointer-events-none disabled:text-muted-foreground"
                    disabled={running || filteredReady.length === 0 || filteredReady.every((d) => selected.includes(d.id))}
                    onClick={() => setSelected([...new Set([...selected, ...filteredReady.map((d) => d.id)])])}
                  >
                    Select {docFilter ? "shown" : "all"}
                  </button>
                  <button
                    type="button"
                    className="bg-none p-0 text-primary hover:underline disabled:pointer-events-none disabled:text-muted-foreground"
                    disabled={running || selected.length === 0}
                    onClick={() => setSelected(docFilter ? selected.filter((id) => !filteredReady.some((d) => d.id === id)) : [])}
                  >
                    Clear {docFilter ? "shown" : "all"}
                  </button>
                </div>
              </div>
              <ul className="m-0 max-h-[260px] list-none overflow-y-auto p-0" role="group" aria-labelledby="docs-label">
                {filteredReady.length === 0 ? (
                  <li className="px-3 py-3.5 text-sm text-muted-foreground">No documents match "{docFilter}".</li>
                ) : (
                  filteredReady.map((d) => {
                    const on = selected.includes(d.id);
                    return (
                      <li key={d.id} className="border-b border-border last:border-none">
                        <label className={cn("flex cursor-pointer items-center gap-2.5 px-3 py-2.5 text-[13px] text-foreground/80", on && "bg-muted text-foreground")}>
                          <Checkbox
                            checked={on}
                            disabled={running || (on && selected.length === 1)}
                            onCheckedChange={() => setSelected(on ? selected.filter((x) => x !== d.id) : [...selected, d.id])}
                          />
                          <span className="min-w-0 flex-1 break-words">{d.filename}</span>
                          {d.is_sample && <Badge>Sample</Badge>}
                        </label>
                      </li>
                    );
                  })
                )}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Upload a PDF first — there are no ready documents.</p>
          )}
        </div>
        <div className="mt-5">
          <label className="mb-2 block text-[13px] font-medium" htmlFor="research-q">
            Question
          </label>
          <Textarea
            id="research-q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask the same question at every depth…"
            disabled={running}
            className="min-h-20 resize-y"
          />
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-foreground/80">
            <Checkbox checked={includeNoRag} onCheckedChange={(v) => setIncludeNoRag(v === true)} disabled={running} />
            Include a no-retrieval baseline
          </label>
          {running ? (
            <Button variant="secondary" onClick={() => abortRef.current?.abort()}>
              <Square size={13} fill="currentColor" /> Stop
            </Button>
          ) : (
            <Button disabled={!canRun} onClick={run}>
              <Play size={14} /> Run comparison
            </Button>
          )}
        </div>
        <p className="mt-3.5 text-[13px] text-muted-foreground">
          Runs run one after another on the local model, so Top-10 takes noticeably longer. Model, prompt, generation settings,
          embedding model and index are identical for every run — only the number of retrieved passages changes.
        </p>
      </Card>

      {error && (
        <div className="mt-4">
          <Notice tone="error">{error}</Notice>
        </div>
      )}

      {planned.length > 0 && (
        <>
          <div
            className="mt-6 grid gap-3 overflow-x-auto pb-2"
            style={{ gridTemplateColumns: `repeat(${planned.length}, minmax(240px, 1fr))` }}
          >
            {planned.map((p) => (
              <ConditionCard key={p} pending={p} result={results.find((r) => r.condition === p)} />
            ))}
          </div>
          {comparison && (
            <p className="mt-3 text-[13px] text-muted-foreground">
              Saved · {comparison.settings.model.model} · temperature {comparison.settings.model.temperature} ·{" "}
              {comparison.settings.embedding_model} · {comparison.settings.chunk_size_words}-word passages ·{" "}
              {comparison.document_names.join(", ")}. *Lexical check only: a sentence counts as found when most of its words and
              all of its numbers appear in the passages. Correctness is not evaluated because ad-hoc questions have no ground
              truth.
            </p>
          )}
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ benchmark

type Row = { key: keyof ConditionAggregate; label: string; format: (v: number | null) => string; hint: string };

const ROWS: Row[] = [
  { key: "accuracy_normalised_mean", label: "Answer accuracy", format: (v) => num(v), hint: "Rubric 0–2 from required-fact coverage, ÷2" },
  { key: "abstention_rate", label: "Abstained", format: (v) => pct(v), hint: "Said the evidence was insufficient" },
  { key: "context_fact_recall_mean", label: "Fact recall in context", format: (v) => pct(v), hint: "Required facts present in supplied passages" },
  { key: "context_fact_bearing_precision_mean", label: "Fact-bearing passages", format: (v) => pct(v), hint: "Supplied passages containing a required fact" },
  { key: "gold_page_retrieved_rate", label: "Gold page retrieved", format: (v) => pct(v), hint: "Validated questions only" },
  { key: "claims_lexically_supported_rate", label: "Sentences found in context", format: (v) => pct(v), hint: "Lexical heuristic, not entailment" },
  { key: "citation_validity_mean", label: "Valid citation markers", format: (v) => pct(v), hint: "[S#] markers that match a supplied passage" },
  { key: "cites_gold_page_rate", label: "Cites gold page", format: (v) => pct(v), hint: "Validated questions only" },
  { key: "prompt_tokens_mean", label: "Prompt tokens (mean)", format: (v) => (v == null ? "—" : Math.round(v).toLocaleString()), hint: "" },
  { key: "total_ms_median", label: "Total latency (median)", format: (v) => formatMs(v), hint: "Retrieval + generation" },
];

interface BenchmarkRecord {
  question_id: string;
  category: string;
  condition: string;
  question: string;
  ground_truth: string;
  answer?: string;
  error?: string;
  retrieved?: { rank: number; source_label: string; chunk_id: string; document_name: string; pages: number[]; similarity: number; text: string }[];
  generation?: { sources_in_prompt: number };
  latency?: { total_ms: number };
  metrics?: { accuracy: { score: number; missing_facts: string[] } };
}

function QuestionBrowser({ runId, conditions }: { runId: string; conditions: string[] }) {
  const [records, setRecords] = useState<BenchmarkRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [qid, setQid] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    setRecords(null);
    api
      .benchmarkRun(runId)
      .then((r) => {
        if (cancelled) return;
        const recs = r.runs as BenchmarkRecord[];
        setRecords(recs);
        setQid(recs[0]?.question_id ?? "");
      })
      .catch((err) => !cancelled && setError((err as ApiError).message));
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const questions = useMemo(() => {
    const seen = new Map<string, BenchmarkRecord>();
    for (const r of records ?? []) if (!seen.has(r.question_id)) seen.set(r.question_id, r);
    return [...seen.values()];
  }, [records]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!records) return <p className="text-sm text-muted-foreground">Loading runs…</p>;
  const current = questions.find((q) => q.question_id === qid);
  const forQ = records.filter((r) => r.question_id === qid);

  return (
    <div>
      <Select value={qid} onChange={(e) => setQid(e.target.value)} aria-label="Benchmark question" className="w-full">
        {questions.map((q) => (
          <option key={q.question_id} value={q.question_id}>
            {q.question_id} · {q.question}
          </option>
        ))}
      </Select>
      {current && (
        <p className="mt-3 text-sm">
          <span className="text-muted-foreground">Reference answer: </span>
          {current.ground_truth}
        </p>
      )}
      <div
        className="mt-4 grid gap-3 overflow-x-auto pb-2"
        style={{ gridTemplateColumns: `repeat(${forQ.length}, minmax(240px, 1fr))` }}
      >
        {conditions
          .map((c) => forQ.find((r) => r.condition === c))
          .filter(Boolean)
          .map((r) => {
            const rec = r as BenchmarkRecord;
            const included = rec.retrieved?.slice(0, rec.generation?.sources_in_prompt ?? 0) ?? [];
            return (
              <Card key={rec.condition} className="flex min-w-0 flex-col gap-3.5 p-4.5">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-[17px] font-semibold">{label(rec.condition)}</h3>
                  <span className="text-xs tabular-nums text-muted-foreground">{formatMs(rec.latency?.total_ms)}</span>
                </div>
                {rec.error ? (
                  <Notice tone="error">{rec.error}</Notice>
                ) : (
                  <div className="text-sm leading-relaxed">
                    <AnswerText text={rec.answer ?? ""} validLabels={new Set(included.map((c) => c.source_label))} />
                  </div>
                )}
                {rec.metrics && (
                  <dl className="grid gap-1.5 border-t border-border pt-3 text-xs">
                    <div className="flex justify-between gap-2">
                      <dt className="text-muted-foreground">Rubric score</dt>
                      <dd className="text-right tabular-nums">{rec.metrics.accuracy.score} / 2</dd>
                    </div>
                    {rec.metrics.accuracy.missing_facts.length > 0 && (
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Missing facts</dt>
                        <dd className="whitespace-normal text-right">{rec.metrics.accuracy.missing_facts.join("; ")}</dd>
                      </div>
                    )}
                  </dl>
                )}
                {rec.retrieved && rec.retrieved.length > 0 && (
                  <Disclosure summary={rec.condition === "gold" ? "Gold passage" : `Retrieved passages (${rec.retrieved.length})`}>
                    <ul className="m-0 mt-2 list-none p-0">
                      {rec.retrieved.map((c) => (
                        <PassageItem key={c.chunk_id} c={c} showSimilarity={rec.condition !== "gold"} />
                      ))}
                    </ul>
                  </Disclosure>
                )}
              </Card>
            );
          })}
      </div>
    </div>
  );
}

function BenchmarkView({ runs }: { runs: BenchmarkSummary[] }) {
  const [runId, setRunId] = useState(runs[0]?.run_id);
  const [subset, setSubset] = useState<"all" | "validated">("all");
  const run = runs.find((r) => r.run_id === runId) ?? runs[0];
  const data = subset === "all" ? run.by_condition : run.by_condition_validated_subset;
  const conditions = run.conditions.filter((c) => data[c]);
  const ragConditions = conditions.filter((c) => c !== "no_rag");
  const tests = run.paired_tests.filter((t) => t.metric === "accuracy_score" && t.p_value != null);

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {runs.length > 1 ? (
          <Select value={run.run_id} onChange={(e) => setRunId(e.target.value)} aria-label="Benchmark run">
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} · {r.question_count} questions · {r.status}
              </option>
            ))}
          </Select>
        ) : (
          <span className="text-[13px] text-muted-foreground">Run {run.run_id}</span>
        )}
        <div className="inline-flex gap-0.5 rounded-md bg-secondary p-0.5">
          <button
            type="button"
            aria-pressed={subset === "all"}
            className={cn("rounded-md px-3 py-1 text-[13px] text-foreground/80", subset === "all" && "bg-card text-foreground shadow-xs")}
            onClick={() => setSubset("all")}
          >
            All {run.question_count} questions
          </button>
          <button
            type="button"
            aria-pressed={subset === "validated"}
            className={cn("rounded-md px-3 py-1 text-[13px] text-foreground/80", subset === "validated" && "bg-card text-foreground shadow-xs")}
            onClick={() => setSubset("validated")}
          >
            {run.validated_question_count} with validated gold page
          </button>
        </div>
      </div>

      {run.status === "partial" && (
        <div className="mb-4">
          <Notice tone="warn">
            This run is incomplete ({run.completed_runs} of {run.planned_runs} runs). Figures cover completed runs only.
          </Notice>
        </div>
      )}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-3">
        <BarChart
          title="Answer accuracy"
          subtitle="Mean rubric score ÷ 2 (lexical required-fact coverage)"
          max={1}
          bars={conditions.map((c) => ({
            label: label(c),
            value: data[c].accuracy_normalised_mean,
            display: num(data[c].accuracy_normalised_mean),
            detail: `n = ${data[c].n} · scores 0/1/2: ${["0", "1", "2"].map((s) => data[c].accuracy_score_counts[s] ?? 0).join(" / ")}`,
          }))}
        />
        <BarChart
          title="Median total latency"
          subtitle="Retrieval + generation, seconds, on this machine"
          bars={conditions.map((c) => ({
            label: label(c),
            value: data[c].total_ms_median,
            display: formatMs(data[c].total_ms_median),
            detail: `mean ${formatMs(data[c].total_ms_mean)} · ${Math.round(data[c].prompt_tokens_mean ?? 0).toLocaleString()} prompt tokens`,
          }))}
        />
        <BarChart
          title="Required facts present in context"
          subtitle="Share of required facts found in the supplied passages"
          max={1}
          bars={ragConditions.map((c) => ({
            label: label(c),
            value: data[c].context_fact_recall_mean,
            display: pct(data[c].context_fact_recall_mean),
            detail: `n = ${data[c].n}`,
          }))}
        />
      </div>

      <h3 className="mb-2.5 mt-7 text-[15px] font-semibold">All measures</h3>
      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full border-collapse text-[13px] tabular-nums">
          <thead>
            <tr>
              <th scope="col" className="sticky top-0 whitespace-nowrap border-b border-border bg-muted px-3.5 py-2.5 text-left font-medium text-muted-foreground">
                Measure
              </th>
              {conditions.map((c) => (
                <th key={c} scope="col" className="sticky top-0 whitespace-nowrap border-b border-border bg-muted px-3.5 py-2.5 text-right font-medium text-muted-foreground">
                  {label(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-left">Runs (errors)</td>
              {conditions.map((c) => (
                <td key={c} className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-right">
                  {data[c].n} ({data[c].errors})
                </td>
              ))}
            </tr>
            {ROWS.map((row) => (
              <tr key={row.key}>
                <td title={row.hint} className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-left last:border-none">
                  {row.label}
                </td>
                {conditions.map((c) => {
                  const v = data[c][row.key] as number | null;
                  return (
                    <td key={c} className={cn("whitespace-nowrap border-b border-border px-3.5 py-2.5 text-right last:border-none", v == null && "text-muted-foreground")}>
                      {row.format(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="mb-1.5 mt-7 text-[15px] font-semibold">Paired tests on accuracy</h3>
      <p className="mb-2.5 text-[13px] text-muted-foreground">
        Wilcoxon signed-rank on per-question rubric scores, Holm-corrected across pairs. Computed on all questions in the run.
      </p>
      {tests.length ? (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full border-collapse text-[13px] tabular-nums">
            <thead>
              <tr>
                {["Pair", "n", "Mean A", "Mean B", "B − A", "p", "p (Holm)"].map((h, i) => (
                  <th
                    key={h}
                    scope="col"
                    className={cn(
                      "sticky top-0 whitespace-nowrap border-b border-border bg-muted px-3.5 py-2.5 font-medium text-muted-foreground",
                      i === 0 ? "text-left" : "text-right",
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tests.map((t) => (
                <tr key={`${t.a}-${t.b}`}>
                  <td className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-left last:border-none">
                    {label(t.a)} vs {label(t.b)}
                  </td>
                  <td className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-right last:border-none">{t.n}</td>
                  <td className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-right last:border-none">{num(t.mean_a)}</td>
                  <td className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-right last:border-none">{num(t.mean_b)}</td>
                  <td className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-right last:border-none">{num(t.mean_diff_b_minus_a)}</td>
                  <td className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-right last:border-none">{t.p_value?.toFixed(4)}</td>
                  <td className="whitespace-nowrap border-b border-border px-3.5 py-2.5 text-right last:border-none">{t.p_holm?.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-[13px] text-muted-foreground">No testable pairs yet (needs at least six paired questions with differing scores).</p>
      )}

      <Card className="mt-7 p-6">
        <h3 className="mb-2.5 text-[15px] font-semibold">Read these numbers with care</h3>
        <ul className="m-0 grid list-disc gap-1.5 pl-[18px] text-[13px] text-foreground/80">
          <li>{run.benchmark_note}</li>
          <li>
            Automatic page-reference validation: {Object.entries(run.validation_counts).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ")}.
            The gold-page condition only covers the validated questions.
          </li>
          <li>{run.evaluation.limitations}</li>
          <li>"Sentences found in context" is a word-overlap check. It cannot detect contradictions, and "not found" does not mean false.</li>
          <li>
            Same model ({run.model.model}, temperature {run.model.temperature}), prompt ({run.prompt_version}), {run.embedding_model} embeddings and{" "}
            {run.chunk_size_words}/{run.chunk_overlap_words}-word passages in every condition. The no-retrieval baseline necessarily uses a
            different, context-free prompt.
          </li>
          <li>Latency was measured on one machine with other work running; compare conditions within this run only.</li>
        </ul>
      </Card>

      <h3 className="mb-2.5 mt-7 text-[15px] font-semibold">Inspect individual questions</h3>
      <QuestionBrowser runId={run.run_id} conditions={run.conditions} />
    </>
  );
}

// ------------------------------------------------------------------ page

export function Research() {
  const { documents } = useDocuments();
  const [results, setResults] = useState<{ comparisons: ComparisonSummary[]; benchmark_runs: BenchmarkSummary[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<Comparison | null>(null);

  const refresh = () =>
    api
      .researchResults()
      .then((r) => {
        setResults(r);
        setError(null);
      })
      .catch((err) => setError((err as ApiError).message));

  useEffect(() => {
    refresh();
  }, []);

  const openComparison = async (id: string) => {
    try {
      setLoaded(await api.comparison(id));
      document.getElementById("compare-title")?.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const fullRuns = results?.benchmark_runs ?? [];

  return (
    <main className="mx-auto max-w-[1080px] px-6 pb-24 pt-[72px]">
      <section>
        <p className="mb-2 text-[13px] font-medium text-muted-foreground">Research</p>
        <h1 className="text-[clamp(30px,4.5vw,40px)] tracking-[-0.025em]">How much context does a good answer need?</h1>
        <p className="mt-3 max-w-[62ch] text-[17px] text-muted-foreground">
          Ask one question at several retrieval depths and compare what the local model does with 1, 3, 5 or 10 passages. Every
          run uses the same retrieval engine as the chat.
        </p>
      </section>

      {error && (
        <div className="mt-6">
          <Notice tone="error">{error}</Notice>
        </div>
      )}

      <LiveCompare documents={documents ?? []} onSaved={refresh} loaded={loaded} />

      <section className="mt-[72px]" aria-labelledby="bench-title">
        <div className="mb-4 flex items-baseline justify-between gap-4">
          <h2 id="bench-title" className="text-xl font-semibold">
            Benchmark results
          </h2>
        </div>
        {!results ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : fullRuns.length === 0 ? (
          <Card className="p-6">
            <p className="font-medium">Experiment not run</p>
            <p className="mt-1.5 text-sm text-muted-foreground">
              No benchmark results exist yet. Run the 50-question benchmark against the bundled sample PDFs from the repository
              root:
            </p>
            <pre className="mt-3 whitespace-pre-wrap font-mono text-[0.86em] text-sm">
              python -m backend.app.research.benchmark ingest{"\n"}python -m backend.app.research.benchmark run
            </pre>
          </Card>
        ) : (
          <BenchmarkView runs={fullRuns} />
        )}
      </section>

      {results && results.comparisons.length > 0 && (
        <section className="mt-[72px]" aria-labelledby="history-title">
          <div className="mb-4 flex items-baseline justify-between gap-4">
            <h2 id="history-title" className="text-xl font-semibold">
              Saved comparisons
            </h2>
          </div>
          <ul className="m-0 list-none border-t border-border p-0">
            {results.comparisons.map((c) => (
              <li key={c.id} className="border-b border-border">
                <button type="button" className="flex w-full items-center justify-between gap-4 bg-none px-1 py-3 text-left" onClick={() => openComparison(c.id)}>
                  <span className="overflow-hidden text-ellipsis whitespace-nowrap text-sm hover:text-primary">{c.question}</span>
                  <span className="whitespace-nowrap text-[13px] text-muted-foreground">
                    {c.document_names.join(", ")} · {formatDate(c.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
