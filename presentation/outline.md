# ContextLens — Presentation Outline (10 Slides)

## Slide 1: Title
**ContextLens — Does More Context Make AI Smarter?**
- M.Tech Modern AI Mini-Project
- Investigating impact of retrieval depth K on RAG quality
- IIT Roorkee documents: PG + PhD brochures (62 pages)
- K ∈ {1,3,5,10}
- Name, Date, Lab

Visual: Hero with CONTEXTLENS big typography, K cards, tagline.

## Slide 2: Problem
**Problem: RAG systems assume more context = better**
- RAG retrieves Top-K chunks → LLM generates answer
- Common practice: increase K for better coverage
- But more context can add:
  - Irrelevant info (noise)
  - Contradictory passages
  - Higher latency
  - LLM confusion / hallucination
- Need empirical investigation, not assumption

Visual: Diagram of RAG pipeline with question mark on "Does more context help?"

## Slide 3: Research Question + Hypothesis
**RQ: Does increasing retrieved chunks always improve answer quality?**

Hypotheses:
- H1 Accuracy: Improve up to point, then diminishing returns / noise
- H2 Relevance/Hallucination: Avg relevance decreases with larger K; hallucination may increase
- H3 Latency: Response time increases with K, especially generation

Metrics: Accuracy, Context Relevance, Hallucination Rate, Response Time

Experimental validity: Only K changes, everything else constant.

Visual: Table of K vs expected trends, metrics definitions.

## Slide 4: Dataset + Benchmark
**Dataset: IIT Roorkee Official Academic Documents**
- Information_Brochure_2026.pdf: 25 pages, 57 PG programmes, eligibility, sponsored
- PhD_IB_A2026.pdf: 37 pages, FTRS/PTRS/Golden Girl, MEQ, departments
- Total: 62 pages, 2 docs

**Benchmark: 50 Questions**
- 15 direct factual (e.g., "When was IITR designated as IIT?")
- 10 procedural (e.g., "How to apply?")
- 10 eligibility (e.g., "60% for General?")
- 5 conditional (e.g., "If 58% General, eligible?")
- 5 numerical (e.g., "How many pages?")
- 5 multi-part (e.g., "Explain FTRS vs PTRS")

Each: question_id, question, category, ground_truth, required_facts, source_doc, page.

Visual: Donut chart of categories, sample Q/A, source doc thumbnails.

## Slide 5: RAG Architecture
**Pipeline: Research-oriented, not just chatbot**

Steps:
1. PDFs → Preprocessing (pypdf, cleaning, hyphen fix, para preserve) → pages.jsonl
2. Chunking (500w, 80 overlap, para-aware, same chunks for all K) → chunks.jsonl
3. Embeddings (all-MiniLM-L6-v2, 384d, FAISS IndexFlatIP, cosine) → embeddings.npy + faiss.index
4. Retrieval (query embedding, top-K, similarity scores) → ranked chunks
5. Generation (LLM, faithful, cited [Doc, p. X], "Insufficient info" if needed, provider abstraction: openai/groq/ollama/mock)
6. Evaluation (accuracy 0-2, relevance 0-3, hallucination claim-level, latency ms)

Visual: Interactive diagram (PDF → Pages → Chunks → Embeddings → FAISS → Query → Top-K → LLM → Answer → Eval)

## Slide 6: Experimental Setup
**Controlled Experiment: K is only variable**

- Independent: K ∈ {1,3,5,10}
- Dependent: accuracy, relevance, hallucination, response time
- Constants: docs, preprocessing, chunks, embedding, FAISS, metric, questions, ground truth, LLM, prompt, gen params, eval method
- Design: Paired — same question at all K, question as unit → Wilcoxon signed-rank, Holm correction
- Runs: 50×4=200 (pilot 5×4=20 before full)
- Outputs: raw_runs.jsonl, results.csv, comparison_table.csv, question_level_results.csv, failure_cases.json, figures/

Visual: Table showing constants vs variable, 200 runs grid, pilot report screenshot.

## Slide 7: Results (Auto-populated from actual experiment)
**Observed Results — No winner labeling, neutral language**

Show 4 charts:
- Accuracy vs K (error bars)
- Relevance vs K
- Hallucination vs K
- Response Time vs K

Table: Aggregated by K:
- Mean accuracy, std, median
- Mean relevance
- Mean hallucination
- Mean response time

Use actual numbers from `results/comparison_table.csv`. Do NOT fabricate.

Example narrative (replace with real):
- "Observed result: Accuracy increased from K=1 to K=3 by +0.12, then plateaued"
- "Measured change: Relevance decreased from 0.85 at K=1 to 0.62 at K=10"
- "Difference from K=1: Response time +180% at K=10"

Include error bars, statistical significance where applicable (p-values, corrected).

Visual: 4 charts, comparison table, note about statistical tests.

## Slide 8: Failure Cases
**Interesting examples identified automatically**

Categories:
- More context introduced irrelevant info (relevance drop)
- Top-1 missed important passage (accuracy low at K=1, high at K=3+)
- Top-5 contradictory passages (hallucination increase)
- Top-10 latency substantially higher
- Correct context retrieved but LLM ignored it
- Unsupported claims
- Duplicate/near-duplicate chunks

For each: Question, K, answer, retrieved context, metrics, failure_type, explanation (evidence-based, not invented).

Visual: 2-3 failure case cards with question, answers at different K, metrics, explanation.

## Slide 9: Findings + Limitations
**Findings (based on measured results, not assumption)**

Summarize observed patterns:
- Does more context help? Depends on metric.
- Accuracy vs K trend
- Relevance vs K trend
- Hallucination vs K trend
- Latency vs K trend
- Statistical significance (Wilcoxon, Holm)

**Limitations:**
- 2 docs, 62 pages, domain-specific
- MiniLM lightweight
- Rule-based eval (human eval better)
- Mock fallback when no LLM key
- Fixed chunking 500/80
- 50 Qs moderate power

Visual: Bullet points, limitation icons, future work hints.

## Slide 10: Conclusion + Future Work
**Conclusion:**
- K is critical hyperparameter, not just "more is better"
- Tradeoff: coverage vs noise vs latency vs faithfulness
- Experimental validity matters: keep everything constant except K
- Research tool built: preprocessing, chunking, embeddings, FAISS, RAG, eval, experiment, FastAPI, Next.js dashboard

**Future Work:**
- Adaptive K based on query complexity/confidence
- Compare embeddings (MPNet, E5, BGE) + re-ranking
- Context compression: summarize Top-10
- Human eval
- Multi-hop questions
- Cost vs quality
- Larger K (20,50) + diverse LLMs

**Demo:** Live experiment lab, inspector, dashboard

**Links:** Backend http://localhost:8000, Frontend http://localhost:3000, GitHub, Results

Visual: Conclusion bullets, future work roadmap, QR to dashboard, thank you.

---

### Notes for Presenter

- Do not fabricate results — use actual `results/comparison_table.csv` and figures
- Emphasize experimental validity: same chunks for all K
- Show pilot before full
- Show failure cases as learning, not just success
- Use neutral language: "Observed result" not "Best"
- Be ready to run live experiment during presentation
- Have validation report ready
- Mention LLM provider abstraction and mock fallback

### Technical Backup Slides (optional)

- Preprocessing stats
- Chunking stats
- Embedding model details
- Retrieval similarity distribution
- Question-level heatmap
- Statistical analysis table (p-values)
- System architecture deep dive
- API endpoints
- Frontend pages

