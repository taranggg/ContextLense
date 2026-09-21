export default function AboutPage() {
  return (
    <div className="space-y-6 max-w-4xl">
      <div className="card p-8">
        <div className="text-[10px] font-mono tracking-widest text-zinc-500">ABOUT THE RESEARCH</div>
        <h1 className="text-3xl font-mono font-black mt-4">Does more context make AI smarter?</h1>
        
        <div className="mt-8 space-y-8">
          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">RESEARCH QUESTION</h2>
            <p className="mt-3 text-lg font-mono text-zinc-200">Does increasing the number of retrieved chunks in a RAG system always improve answer quality?</p>
            <p className="mt-3 text-sm text-zinc-400 leading-relaxed">We experimentally compare Top-1, Top-3, Top-5, Top-10 retrieved chunks and measure Answer Accuracy, Context Relevance, Hallucination Rate, Response Time. We do NOT assume more context is better.</p>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">HYPOTHESIS</h2>
            <div className="mt-3 grid md:grid-cols-3 gap-3">
              <div className="border border-[#262626] rounded-xl p-4 bg-[#0a0a0a]">
                <div className="text-[10px] font-mono text-zinc-500">H1: ACCURACY</div>
                <div className="text-xs mt-2 text-zinc-300">More context may improve accuracy up to a point, but beyond K=5, diminishing returns or noise introduction.</div>
              </div>
              <div className="border border-[#262626] rounded-xl p-4 bg-[#0a0a0a]">
                <div className="text-[10px] font-mono text-zinc-500">H2: RELEVANCE & HALLUCINATION</div>
                <div className="text-xs mt-2 text-zinc-300">Average relevance may decrease with larger K as later chunks are less relevant; hallucination may increase due to contradictory passages.</div>
              </div>
              <div className="border border-[#262626] rounded-xl p-4 bg-[#0a0a0a]">
                <div className="text-[10px] font-mono text-zinc-500">H3: LATENCY</div>
                <div className="text-xs mt-2 text-zinc-300">Response time increases with K, especially generation time due to longer prompts.</div>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">EXPERIMENTAL SETUP</h2>
            <div className="mt-3 text-sm text-zinc-300 leading-relaxed">
              <p>50 questions × 4 K values = 200 runs. Every run records question_id, k, retrieved_chunks, generated_answer, retrieval_time, generation_time, total_time, accuracy, relevance, hallucination, source docs/pages.</p>
              <p className="mt-2">Independent variable: K. Constants: docs, preprocessing, chunks, embedding, vector DB, similarity, questions, ground truth, LLM, prompt, generation params, eval method.</p>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">LIMITATIONS</h2>
            <ul className="mt-3 list-disc list-inside text-sm text-zinc-400 space-y-1">
              <li>Dataset limited to 2 IITR brochures (62 pages) — domain-specific, not general web.</li>
              <li>Embedding model MiniLM-L6-v2 is lightweight; larger models may change retrieval quality.</li>
              <li>Evaluation uses rule-based + optional LLM judge; human evaluation would be more reliable.</li>
              <li>Mock LLM fallback when no API key: extractive, not generative — real LLM may behave differently.</li>
              <li>Chunk size 500w/80 overlap is fixed; other chunking strategies not tested.</li>
              <li>Sample size 50 questions — moderate power for statistical tests; Wilcoxon used but effect sizes matter more.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">FUTURE WORK</h2>
            <ul className="mt-3 list-disc list-inside text-sm text-zinc-400 space-y-1">
              <li>Test adaptive retrieval: dynamic K based on query complexity or confidence.</li>
              <li>Compare embedding models (MPNet, E5, BGE) and re-ranking (cross-encoder).</li>
              <li>Investigate context compression: summarization of Top-10 to reduce noise while keeping coverage.</li>
              <li>Human evaluation for relevance and hallucination.</li>
              <li>Extend to multi-hop questions requiring synthesis across distant chunks.</li>
              <li>Measure cost vs quality tradeoff (tokens, latency, accuracy).</li>
              <li>Test with larger K (20, 50) and with diverse LLMs.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-mono font-bold tracking-widest">CITATIONS</h2>
            <div className="mt-3 text-[11px] font-mono text-zinc-500 space-y-1">
              <div>• Lewis et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.</div>
              <div>• Reimers & Gurevych (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. EMNLP.</div>
              <div>• Johnson et al. (2019). Billion-scale similarity search with GPUs. IEEE Big Data. (FAISS)</div>
              <div>• Es et al. (2024). RAGAS: Automated Evaluation of Retrieval Augmented Generation. arXiv.</div>
              <div>• Primary data: IIT Roorkee PG Information Brochure 2026, PhD IB Autumn 2026 (official).</div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
