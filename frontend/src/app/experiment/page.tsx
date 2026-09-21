"use client"
import { useState, useEffect } from "react"
import { API_URL } from "@/lib/utils"
import { PipelineViz } from "@/components/PipelineViz"
import { MetricCard } from "@/components/MetricCard"
import { motion } from "framer-motion"

type Chunk = {
  rank: number
  chunk_id: string
  document: string
  page: number
  text: string
  similarity: number
}

type KResult = {
  k: number
  answer: string
  retrieved_chunks: Chunk[]
  metrics: {
    context_relevance: number
    hallucination_rate: number
    response_time_ms: number
    retrieval_time_ms: number
    generation_time_ms: number
  }
  sources: any[]
}

export default function ExperimentLab() {
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<KResult[]>([])
  const [benchmarkQs, setBenchmarkQs] = useState<any[]>([])
  const [activeStep, setActiveStep] = useState("question")

  useEffect(() => {
    fetch(`${API_URL}/api/benchmark`).then(r=>r.json()).then(d=>setBenchmarkQs(d.questions || [])).catch(()=>{})
  }, [])

  const runExperiment = async () => {
    if (!question.trim()) return
    setLoading(true)
    setActiveStep("embedding")
    try {
      // Simulate pipeline progression
      setTimeout(()=>setActiveStep("search"), 300)
      setTimeout(()=>setActiveStep("topk"), 600)
      setTimeout(()=>setActiveStep("llm"), 900)

      const res = await fetch(`${API_URL}/api/experiment`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({question})
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setResults(data.results)
      setActiveStep("answer")
    } catch (e:any) {
      alert("Experiment failed: " + e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid lg:grid-cols-[380px_1fr] gap-6">
      {/* Left */}
      <div className="space-y-4">
        <div className="card p-5">
          <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-3">QUESTION INPUT</div>
          <textarea
            value={question}
            onChange={e=>setQuestion(e.target.value)}
            placeholder="e.g. What is the minimum percentage required for General category for M.Tech?"
            className="w-full h-32 bg-[#0a0a0a] border border-[#262626] rounded-xl p-3 text-sm font-mono focus:border-[#ff3b30] outline-none resize-none"
          />
          <button
            onClick={runExperiment}
            disabled={loading || !question.trim()}
            className="mt-3 w-full bg-[#ff3b30] text-black py-3 rounded-xl font-mono font-bold text-xs tracking-widest disabled:opacity-50 hover:bg-[#ff5a52] transition-colors"
          >
            {loading ? "RUNNING EXPERIMENT..." : "RUN EXPERIMENT • K=1,3,5,10"}
          </button>
          <div className="mt-2 text-[10px] font-mono text-zinc-500">Will execute 4 RAG runs in parallel (same question, different K)</div>
        </div>

        <PipelineViz activeStep={activeStep} />

        <div className="card p-5">
          <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-3">EXAMPLE QUESTIONS • BENCHMARK</div>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {benchmarkQs.slice(0,12).map((q:any) => (
              <button
                key={q.question_id}
                onClick={()=>setQuestion(q.question)}
                className="w-full text-left border border-[#262626] rounded-lg p-2 hover:border-[#404040] transition-colors"
              >
                <div className="text-[9px] font-mono text-zinc-500">{q.question_id} • {q.category}</div>
                <div className="text-[11px] text-zinc-300 mt-1 line-clamp-2">{q.question}</div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right */}
      <div className="space-y-4">
        {results.length===0 ? (
          <div className="card p-12 text-center">
            <div className="text-6xl mb-4">🧪</div>
            <div className="font-mono font-bold">EXPERIMENT LAB</div>
            <div className="text-sm text-zinc-500 mt-2 max-w-md mx-auto">Enter a question and run the experiment. You'll see 4 columns for TOP-1, TOP-3, TOP-5, TOP-10 with retrieved chunks, similarity, sources, answer, and metrics.</div>
            <div className="mt-6 grid grid-cols-4 gap-2 max-w-md mx-auto">
              {[1,3,5,10].map(k=>(
                <div key={k} className="border border-dashed border-[#262626] rounded-xl p-3">
                  <div className="text-[10px] font-mono text-zinc-600">TOP-{k}</div>
                  <div className="text-xs font-mono mt-1 text-zinc-400">Waiting</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
            {results.sort((a,b)=>a.k-b.k).map(r => (
              <motion.div key={r.k} initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} className="card p-4 flex flex-col">
                <div className="flex justify-between items-center">
                  <div className="text-[10px] font-mono tracking-widest text-zinc-500">TOP-{r.k}</div>
                  <div className="text-[9px] font-mono px-1.5 py-0.5 bg-[#1a1a1a] border border-[#262626] rounded">{r.retrieved_chunks.length} CHUNKS</div>
                </div>

                <div className="mt-3 space-y-2">
                  <MetricCard label="CONTEXT RELEVANCE" value={r.metrics.context_relevance.toFixed(2)} sub={`${(r.metrics.context_relevance*100).toFixed(0)}% relevant`} className="p-3" />
                  <div className="grid grid-cols-2 gap-2">
                    <MetricCard label="HALLUCINATION" value={r.metrics.hallucination_rate.toFixed(2)} className="p-2" />
                    <MetricCard label="RESPONSE TIME" value={`${r.metrics.response_time_ms.toFixed(0)}ms`} className="p-2" />
                  </div>
                </div>

                <div className="mt-4">
                  <div className="text-[10px] font-mono text-zinc-500">GENERATED ANSWER</div>
                  <div className="mt-2 bg-[#0a0a0a] border border-[#262626] rounded-xl p-3 text-xs leading-relaxed max-h-[200px] overflow-y-auto">
                    {r.answer}
                  </div>
                </div>

                <div className="mt-4">
                  <div className="text-[10px] font-mono text-zinc-500 mb-2">RETRIEVED CHUNKS</div>
                  <div className="space-y-2 max-h-[300px] overflow-y-auto">
                    {r.retrieved_chunks.map(c=>(
                      <div key={c.chunk_id} className="border border-[#262626] rounded-lg p-2 bg-[#0a0a0a]">
                        <div className="flex justify-between text-[9px] font-mono">
                          <span className="text-zinc-500">RANK {c.rank} • {c.document} p.{c.page}</span>
                          <span className="text-[#ff3b30]">{c.similarity.toFixed(3)}</span>
                        </div>
                        <div className="text-[11px] text-zinc-300 mt-1 line-clamp-3">{c.text}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-[#262626] grid grid-cols-2 gap-2 text-[9px] font-mono text-zinc-500">
                  <div>RET: {r.metrics.retrieval_time_ms.toFixed(0)}ms</div>
                  <div>GEN: {r.metrics.generation_time_ms.toFixed(0)}ms</div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
