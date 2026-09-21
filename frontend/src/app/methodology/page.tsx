export default function MethodologyPage() {
  return (
    <div className="space-y-6 max-w-4xl">
      <div className="card p-8">
        <div className="text-[10px] font-mono tracking-widest text-zinc-500">METHODOLOGY • EXPERIMENTAL VALIDITY</div>
        <h1 className="text-3xl font-mono font-black mt-4">How ContextLens Works</h1>
        
        <div className="mt-8 space-y-8">
          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">DATASET</h2>
            <div className="mt-3 text-sm text-zinc-300 leading-relaxed space-y-2">
              <p>Primary sources: IIT Roorkee PG Information Brochure 2026 (25 pages) + PhD IB Autumn 2026 (37 pages). Total 62 pages, official academic documents.</p>
              <p>Benchmark: 50 questions categorized as 15 direct factual, 10 procedural, 10 eligibility, 5 conditional, 5 numerical, 5 multi-part. Each contains ground_truth, required_facts, source_document, source_page.</p>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">CHUNKING</h2>
            <div className="mt-3 text-sm text-zinc-300 leading-relaxed">
              <p>Section-aware chunking: ~500 words per chunk, ~80 words overlap. Prioritizes paragraph boundaries over blind cutting. Same chunks used for all K values — critical for experimental validity.</p>
              <div className="mt-3 bg-[#0a0a0a] border border-[#262626] rounded-xl p-3 font-mono text-xs">
                chunk_size=500, overlap=80, preserve_paragraphs=True, no cross-page merging
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">EMBEDDING MODEL</h2>
            <div className="mt-3 text-sm text-zinc-300 leading-relaxed">
              <p>Default: sentence-transformers/all-MiniLM-L6-v2 (384 dim). Configurable via env. Generates embeddings for every chunk, stored efficiently (npy + FAISS). Does not recompute on startup.</p>
              <p className="mt-2">Fallback: TF-IDF (384 features, stopwords english, ngram 1-2, L2 normalized) for offline testing when torch unavailable.</p>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">VECTOR SEARCH</h2>
            <div className="mt-3 text-sm text-zinc-300 leading-relaxed">
              <p>FAISS IndexFlatIP for cosine similarity (inner product on normalized vectors). Query embedding → search → ranked chunks with similarity scores.</p>
              <p className="mt-2">Supports K=1,3,5,10. UI displays retrieved chunks with rank, doc, page, similarity, text.</p>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">RAG GENERATION</h2>
            <div className="mt-3 text-sm text-zinc-300 leading-relaxed">
              <p>LLM must ONLY answer using retrieved context. Prompt includes user question, retrieved context, source metadata. Answer includes citations [Doc, p. X]. If insufficient info, says "Insufficient information in the provided documents." — no guessing.</p>
              <div className="mt-3 bg-[#0a0a0a] border border-[#262626] rounded-xl p-3 font-mono text-xs">
                System: You are helpful assistant for IIT Roorkee... Answer ONLY using context... Cite sources...<br/>
                Provider abstraction: openai, groq, openrouter, ollama, mock (extractive fallback)
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">EVALUATION METRICS</h2>
            <div className="mt-3 grid md:grid-cols-2 gap-4">
              <div className="border border-[#262626] rounded-xl p-4 bg-[#0a0a0a]">
                <div className="text-xs font-mono font-bold">Answer Accuracy (0-2 → normalized 0-1)</div>
                <div className="text-[11px] text-zinc-400 mt-2">0=incorrect/missing, 1=partially correct, 2=correct & complete. Normalized: sum(scores)/(2*num_q). Uses required_facts coverage. Optional LLM judge with strict JSON schema.</div>
              </div>
              <div className="border border-[#262626] rounded-xl p-4 bg-[#0a0a0a]">
                <div className="text-xs font-mono font-bold">Context Relevance (0-3 per chunk)</div>
                <div className="text-[11px] text-zinc-400 mt-2">0=irrelevant, 1=weakly related, 2=useful, 3=directly useful. Aggregate: sum(scores)/(3*K). Distinguishes similarity from human-judged relevance.</div>
              </div>
              <div className="border border-[#262626] rounded-xl p-4 bg-[#0a0a0a]">
                <div className="text-xs font-mono font-bold">Hallucination Rate (claim-level)</div>
                <div className="text-[11px] text-zinc-400 mt-2">Extract factual claims → compare against retrieved evidence → label SUPPORTED/UNSUPPORTED/CONTRADICTED. Rate = (UNSUPPORTED+CONTRADICTED)/TOTAL.</div>
              </div>
              <div className="border border-[#262626] rounded-xl p-4 bg-[#0a0a0a]">
                <div className="text-xs font-mono font-bold">Response Time (ms)</div>
                <div className="text-[11px] text-zinc-400 mt-2">Measured separately: retrieval_time_ms, generation_time_ms, total_response_time_ms using high-res Python timing. No fake times.</div>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">EXPERIMENTAL DESIGN • CRITICAL RULE</h2>
            <div className="mt-3 text-sm text-zinc-300 leading-relaxed">
              <p>Independent variable: RETRIEVAL DEPTH K ∈ {'{1,3,5,10}'} — only K changes. Everything else constant:</p>
              <ul className="mt-2 list-disc list-inside text-xs font-mono text-zinc-400 space-y-1">
                <li>same documents</li>
                <li>same preprocessing</li>
                <li>same chunks</li>
                <li>same embedding model</li>
                <li>same vector DB</li>
                <li>same similarity metric</li>
                <li>same questions & ground truth</li>
                <li>same LLM, system prompt, generation params</li>
                <li>same evaluation methodology</li>
              </ul>
              <p className="mt-3">Paired design: question as experimental unit. Wilcoxon signed-rank tests where appropriate, Holm correction for multiple comparisons. Report effect direction, p-value, corrected p-value, effect size. No overclaiming.</p>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">INTERACTIVE DIAGRAM</h2>
            <div className="mt-3 border border-[#262626] rounded-xl p-6 bg-[#0a0a0a] font-mono text-xs">
              <div className="flex flex-col items-center gap-2">
                <div className="border border-[#262626] rounded-lg px-4 py-2 bg-[#141414]">PDFs (IITR Brochures)</div>
                <div>↓</div>
                <div className="border border-[#262626] rounded-lg px-4 py-2 bg-[#141414]">Preprocessing (pypdf, cleaning)</div>
                <div>↓</div>
                <div className="border border-[#262626] rounded-lg px-4 py-2 bg-[#141414]">Chunking (500w, 80 overlap, para-aware)</div>
                <div>↓</div>
                <div className="border border-[#262626] rounded-lg px-4 py-2 bg-[#141414]">Embeddings (MiniLM-L6-v2) → FAISS</div>
                <div>↓</div>
                <div className="flex gap-4">
                  <div className="border border-[#ff3b30]/50 rounded-lg px-4 py-2 bg-[#1a0a0a]">Query → Embedding</div>
                  <div className="border border-[#262626] rounded-lg px-4 py-2">Benchmark (50 Qs)</div>
                </div>
                <div>↓</div>
                <div className="grid grid-cols-4 gap-2">
                  <div className="border border-[#262626] rounded-lg px-3 py-2 bg-[#141414] text-center">TOP-1</div>
                  <div className="border border-[#262626] rounded-lg px-3 py-2 bg-[#141414] text-center">TOP-3</div>
                  <div className="border border-[#262626] rounded-lg px-3 py-2 bg-[#141414] text-center">TOP-5</div>
                  <div className="border border-[#262626] rounded-lg px-3 py-2 bg-[#141414] text-center">TOP-10</div>
                </div>
                <div>↓</div>
                <div className="border border-[#262626] rounded-lg px-4 py-2 bg-[#141414]">LLM Generation (cited, faithful)</div>
                <div>↓</div>
                <div className="border border-[#262626] rounded-lg px-4 py-2 bg-[#141414]">Evaluation (Accuracy, Relevance, Hallucination, Latency)</div>
                <div>↓</div>
                <div className="border border-[#ff3b30] rounded-lg px-4 py-2 bg-[#1a0a0a]">Comparison & Statistical Analysis</div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
