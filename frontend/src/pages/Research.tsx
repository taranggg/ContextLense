import { Check, ChevronRight, CircleHelp, Play, Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
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

function ConditionCard({ result, pending }: { result?: ConditionResult; pending: string }) {
  if (!result) {
    return (
      <article className="condition" aria-busy="true">
        <div className="condition-head">
          <h3>{label(pending)}</h3>
        </div>
        <div className="condition-pending">
          <span className="spinner" aria-hidden="true" /> Waiting…
        </div>
      </article>
    );
  }
  const m = result.metrics;
  const included = result.generation ? result.retrieved.slice(0, result.generation.sources_in_prompt) : result.retrieved;
  const valid = new Set(included.map((c) => c.source_label));
  const unsupported = m?.claim_checks.filter((c) => c.label === "unsupported") ?? [];
  return (
    <article className="condition">
      <div className="condition-head">
        <h3>{label(result.condition)}</h3>
        <span className="small muted tabular">{formatMs(result.latency?.total_ms)}</span>
      </div>
      {result.error ? (
        <Notice tone="error">{result.error}</Notice>
      ) : (
        <AnswerText text={result.answer ?? ""} validLabels={valid} />
      )}
      {m && (
        <dl className="metric-list">
          <div>
            <dt>Correctness</dt>
            <dd className="muted">Not evaluated</dd>
          </div>
          <div>
            <dt>Abstained</dt>
            <dd>{m.abstained ? "Yes" : "No"}</dd>
          </div>
          {result.condition !== "no_rag" && (
            <>
              <div>
                <dt>Citations matching a passage</dt>
                <dd>{m.citation_count ? `${m.citation_count - m.invalid_citation_count} of ${m.citation_count}` : "none"}</dd>
              </div>
              <div>
                <dt title="Lexical check: most content words and all numbers of the sentence appear in the supplied passages.">
                  Sentences found in passages*
                </dt>
                <dd>{m.claims_total ? `${m.claims_lexically_supported} of ${m.claims_total}` : "—"}</dd>
              </div>
              <div>
                <dt>Prompt tokens</dt>
                <dd>{result.generation?.prompt_tokens?.toLocaleString() ?? "—"}</dd>
              </div>
            </>
          )}
          <div>
            <dt>Generation</dt>
            <dd>{formatMs(result.latency?.generation_ms)}</dd>
          </div>
        </dl>
      )}
      {result.generation?.context_truncated && (
        <Notice tone="warn">Context trimmed: {result.generation.sources_in_prompt} of {result.retrieved.length} passages fit.</Notice>
      )}
      {unsupported.length > 0 && (
        <details className="disclosure">
          <summary>
            <ChevronRight size={14} /> Not found in passages ({unsupported.length})
          </summary>
          <ul className="claim-list">
            {unsupported.map((c) => (
              <li key={c.claim}>
                <CircleHelp size={13} aria-hidden="true" />
                <span>
                  {c.claim}
                  {c.missing_numbers.length > 0 && <span className="muted"> — numbers not in passages: {c.missing_numbers.join(", ")}</span>}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
      {result.retrieved.length > 0 && (
        <details className="disclosure">
          <summary>
            <ChevronRight size={14} /> Retrieved passages ({result.retrieved.length})
          </summary>
          <ul style={{ padding: 0, margin: "8px 0 0" }}>
            {result.retrieved.map((c) => (
              <li key={c.chunk_id} className="passage" style={{ listStyle: "none" }}>
                <div className="passage-head">
                  <span className="source-label">{c.source_label}</span>
                  <span className="doc">{c.document_name}</span>
                  <span className="muted">{formatPages(c.pages)}</span>
                </div>
                <div style={{ marginTop: 4 }}>
                  <Similarity value={c.similarity} />
                </div>
                <p className="passage-text clamped">{c.text}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

function LiveCompare({ documents, onSaved, loaded }: { documents: DocumentInfo[]; onSaved: () => void; loaded: Comparison | null }) {
  const { readiness } = useReady();
  const ready = documents.filter((d) => d.status === "ready");
  const [selected, setSelected] = useState<string[]>([]);
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

  return (
    <section className="section" aria-labelledby="compare-title">
      <div className="section-head">
        <h2 id="compare-title" className="section-title">
          Compare retrieval depths
        </h2>
      </div>
      <div className="panel">
        <div className="form-row">
          <span className="field-label" id="docs-label">
            Documents
          </span>
          {ready.length ? (
            <div className="chip-select" role="group" aria-labelledby="docs-label">
              {ready.map((d) => {
                const on = selected.includes(d.id);
                return (
                  <button
                    key={d.id}
                    type="button"
                    className="chip"
                    aria-pressed={on}
                    disabled={running || (on && selected.length === 1)}
                    onClick={() => setSelected(on ? selected.filter((x) => x !== d.id) : [...selected, d.id])}
                  >
                    {on && <Check size={13} aria-hidden="true" />}
                    <span>{d.filename}</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="muted small">Upload a PDF first — there are no ready documents.</p>
          )}
        </div>
        <div className="form-row">
          <label className="field-label" htmlFor="research-q">
            Question
          </label>
          <textarea
            id="research-q"
            className="textarea"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask the same question at every depth…"
            disabled={running}
          />
        </div>
        <div className="form-actions">
          <label className="checkbox">
            <input type="checkbox" checked={includeNoRag} onChange={(e) => setIncludeNoRag(e.target.checked)} disabled={running} />
            Include a no-retrieval baseline
          </label>
          {running ? (
            <button type="button" className="btn btn-secondary" onClick={() => abortRef.current?.abort()}>
              <Square size={13} fill="currentColor" /> Stop
            </button>
          ) : (
            <button type="button" className="btn btn-primary" disabled={!canRun} onClick={run}>
              <Play size={14} /> Run comparison
            </button>
          )}
        </div>
        <p className="small muted" style={{ marginTop: 14 }}>
          Runs run one after another on the local model, so Top-10 takes noticeably longer. Model, prompt, generation settings,
          embedding model and index are identical for every run — only the number of retrieved passages changes.
        </p>
      </div>

      {error && (
        <div style={{ marginTop: 16 }}>
          <Notice tone="error">{error}</Notice>
        </div>
      )}

      {planned.length > 0 && (
        <>
          <div className="compare-grid" style={{ ["--cols" as string]: planned.length }}>
            {planned.map((p) => (
              <ConditionCard key={p} pending={p} result={results.find((r) => r.condition === p)} />
            ))}
          </div>
          {comparison && (
            <p className="small muted" style={{ marginTop: 12 }}>
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
  if (!records) return <p className="muted small">Loading runs…</p>;
  const current = questions.find((q) => q.question_id === qid);
  const forQ = records.filter((r) => r.question_id === qid);

  return (
    <div>
      <select className="select" value={qid} onChange={(e) => setQid(e.target.value)} aria-label="Benchmark question" style={{ width: "100%" }}>
        {questions.map((q) => (
          <option key={q.question_id} value={q.question_id}>
            {q.question_id} · {q.question}
          </option>
        ))}
      </select>
      {current && (
        <p className="small" style={{ marginTop: 12 }}>
          <span className="muted">Reference answer: </span>
          {current.ground_truth}
        </p>
      )}
      <div className="compare-grid" style={{ ["--cols" as string]: forQ.length }}>
        {conditions
          .map((c) => forQ.find((r) => r.condition === c))
          .filter(Boolean)
          .map((r) => {
            const rec = r as BenchmarkRecord;
            const included = rec.retrieved?.slice(0, rec.generation?.sources_in_prompt ?? 0) ?? [];
            return (
              <article key={rec.condition} className="condition">
                <div className="condition-head">
                  <h3>{label(rec.condition)}</h3>
                  <span className="small muted tabular">{formatMs(rec.latency?.total_ms)}</span>
                </div>
                {rec.error ? (
                  <Notice tone="error">{rec.error}</Notice>
                ) : (
                  <AnswerText text={rec.answer ?? ""} validLabels={new Set(included.map((c) => c.source_label))} />
                )}
                {rec.metrics && (
                  <dl className="metric-list">
                    <div>
                      <dt>Rubric score</dt>
                      <dd>{rec.metrics.accuracy.score} / 2</dd>
                    </div>
                    {rec.metrics.accuracy.missing_facts.length > 0 && (
                      <div>
                        <dt>Missing facts</dt>
                        <dd style={{ whiteSpace: "normal" }}>{rec.metrics.accuracy.missing_facts.join("; ")}</dd>
                      </div>
                    )}
                  </dl>
                )}
                {rec.retrieved && rec.retrieved.length > 0 && (
                  <details className="disclosure">
                    <summary>
                      <ChevronRight size={14} /> {rec.condition === "gold" ? "Gold passage" : `Retrieved passages (${rec.retrieved.length})`}
                    </summary>
                    <ul style={{ padding: 0, margin: "8px 0 0" }}>
                      {rec.retrieved.map((c) => (
                        <li key={c.chunk_id} className="passage" style={{ listStyle: "none" }}>
                          <div className="passage-head">
                            <span className="source-label">{c.source_label}</span>
                            <span className="doc">{c.document_name}</span>
                            <span className="muted">{formatPages(c.pages)}</span>
                          </div>
                          {rec.condition !== "gold" && (
                            <div style={{ marginTop: 4 }}>
                              <Similarity value={c.similarity} />
                            </div>
                          )}
                          <p className="passage-text clamped">{c.text}</p>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </article>
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
      <div className="form-actions" style={{ marginTop: 0, marginBottom: 16 }}>
        {runs.length > 1 ? (
          <select className="select" value={run.run_id} onChange={(e) => setRunId(e.target.value)} aria-label="Benchmark run">
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} · {r.question_count} questions · {r.status}
              </option>
            ))}
          </select>
        ) : (
          <span className="small muted">Run {run.run_id}</span>
        )}
        <div className="segmented" role="group" aria-label="Question subset">
          <button type="button" aria-pressed={subset === "all"} onClick={() => setSubset("all")}>
            All {run.question_count} questions
          </button>
          <button type="button" aria-pressed={subset === "validated"} onClick={() => setSubset("validated")}>
            {run.validated_question_count} with validated gold page
          </button>
        </div>
      </div>

      {run.status === "partial" && (
        <div style={{ marginBottom: 16 }}>
          <Notice tone="warn">
            This run is incomplete ({run.completed_runs} of {run.planned_runs} runs). Figures cover completed runs only.
          </Notice>
        </div>
      )}

      <div className="chart-grid">
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

      <h3 style={{ fontSize: 15, margin: "28px 0 10px" }}>All measures</h3>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th scope="col">Measure</th>
              {conditions.map((c) => (
                <th key={c} scope="col">
                  {label(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Runs (errors)</td>
              {conditions.map((c) => (
                <td key={c}>
                  {data[c].n} ({data[c].errors})
                </td>
              ))}
            </tr>
            {ROWS.map((row) => (
              <tr key={row.key}>
                <td title={row.hint}>{row.label}</td>
                {conditions.map((c) => {
                  const v = data[c][row.key] as number | null;
                  return (
                    <td key={c} className={v == null ? "na" : ""}>
                      {row.format(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 style={{ fontSize: 15, margin: "28px 0 6px" }}>Paired tests on accuracy</h3>
      <p className="small muted" style={{ marginBottom: 10 }}>
        Wilcoxon signed-rank on per-question rubric scores, Holm-corrected across pairs. Computed on all questions in the run.
      </p>
      {tests.length ? (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th scope="col">Pair</th>
                <th scope="col">n</th>
                <th scope="col">Mean A</th>
                <th scope="col">Mean B</th>
                <th scope="col">B − A</th>
                <th scope="col">p</th>
                <th scope="col">p (Holm)</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((t) => (
                <tr key={`${t.a}-${t.b}`}>
                  <td>
                    {label(t.a)} vs {label(t.b)}
                  </td>
                  <td>{t.n}</td>
                  <td>{num(t.mean_a)}</td>
                  <td>{num(t.mean_b)}</td>
                  <td>{num(t.mean_diff_b_minus_a)}</td>
                  <td>{t.p_value?.toFixed(4)}</td>
                  <td>{t.p_holm?.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="small muted">No testable pairs yet (needs at least six paired questions with differing scores).</p>
      )}

      <div className="panel" style={{ marginTop: 28 }}>
        <h3 style={{ fontSize: 15, marginBottom: 10 }}>Read these numbers with care</h3>
        <ul className="caveats">
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
      </div>

      <h3 style={{ fontSize: 15, margin: "28px 0 10px" }}>Inspect individual questions</h3>
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
    <main className="page">
      <section className="research-intro">
        <p className="eyebrow">Research</p>
        <h1>How much context does a good answer need?</h1>
        <p>
          Ask one question at several retrieval depths and compare what the local model does with 1, 3, 5 or 10 passages. Every
          run uses the same retrieval engine as the chat.
        </p>
      </section>

      {error && (
        <div style={{ marginTop: 24 }}>
          <Notice tone="error">{error}</Notice>
        </div>
      )}

      <LiveCompare documents={documents ?? []} onSaved={refresh} loaded={loaded} />

      <section className="section" aria-labelledby="bench-title">
        <div className="section-head">
          <h2 id="bench-title" className="section-title">
            Benchmark results
          </h2>
        </div>
        {!results ? (
          <p className="muted small">Loading…</p>
        ) : fullRuns.length === 0 ? (
          <div className="panel">
            <p style={{ fontWeight: 500 }}>Experiment not run</p>
            <p className="small muted" style={{ marginTop: 6 }}>
              No benchmark results exist yet. Run the 50-question benchmark against the bundled sample PDFs from the repository
              root:
            </p>
            <pre className="mono small" style={{ marginTop: 12, whiteSpace: "pre-wrap" }}>
              python -m backend.app.research.benchmark ingest{"\n"}python -m backend.app.research.benchmark run
            </pre>
          </div>
        ) : (
          <BenchmarkView runs={fullRuns} />
        )}
      </section>

      {results && results.comparisons.length > 0 && (
        <section className="section" aria-labelledby="history-title">
          <div className="section-head">
            <h2 id="history-title" className="section-title">
              Saved comparisons
            </h2>
          </div>
          <ul className="history-list">
            {results.comparisons.map((c) => (
              <li key={c.id}>
                <button type="button" onClick={() => openComparison(c.id)}>
                  <span className="q">{c.question}</span>
                  <span className="small muted" style={{ whiteSpace: "nowrap" }}>
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
