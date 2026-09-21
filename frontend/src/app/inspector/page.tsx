"use client"
import { useState } from "react"
import { API_URL } from "@/lib/utils"

type Chunk = {
  rank: number
  chunk_id: string
  document: string
  page: number
  text: string
  similarity: number
}

export default function InspectorPage() {
  const [question, setQuestion] = useState("What is the minimum percentage required for General category for M.Tech?")
  const [k, setK] = useState(5)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)

  const inspect = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/query`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({question, k})
      })
      const data = await res.json()
      setChunks(data.retrieved_chunks)
    } catch(e:any) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4">CONTEXT INSPECTOR • RETRIEVAL VISUALIZATION</div>
        <div className="flex gap-3">
          <input value={question} onChange={e=>setQuestion(e.target.value)} className="flex-1 bg-[#0a0a0a] border border-[#262626] rounded-xl px-4 py-3 text-sm font-mono focus:border-[#ff3b30] outline-none" placeholder="Enter question" />
          <select value={k} onChange={e=>setK(parseInt(e.target.value))} className="bg-[#0a0a0a] border border-[#262626] rounded-xl px-3 py-3 text-xs font-mono">
            {[1,3,5,10].map(v=><option key={v} value={v}>TOP-{v}</option>)}
          </select>
          <button onClick={inspect} disabled={loading} className="bg-white text-black px-6 py-3 rounded-xl font-mono font-bold text-xs tracking-widest disabled:opacity-50">
            {loading ? "SEARCHING..." : "INSPECT"}
          </button>
        </div>
      </div>

      {chunks.length>0 && (
        <div className="grid gap-4">
          {chunks.map(c=>(
            <div key={c.chunk_id} className="card p-5">
              <div className="flex justify-between items-start">
                <div className="flex gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[#1a1a1a] border border-[#262626] flex items-center justify-center font-mono font-bold text-sm">#{c.rank}</div>
                  <div>
                    <div className="text-xs font-mono font-bold">{c.document} • Page {c.page}</div>
                    <div className="text-[10px] font-mono text-zinc-500 mt-1">Chunk ID: {c.chunk_id} • Similarity: {c.similarity.toFixed(4)}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-[10px] font-mono px-2 py-1 rounded-full border" style={{borderColor: c.similarity>0.7 ? "#22c55e" : c.similarity>0.4 ? "#eab308" : "#ef4444", color: c.similarity>0.7 ? "#22c55e" : c.similarity>0.4 ? "#eab308" : "#ef4444"}}>
                    {c.similarity>0.7 ? "HIGH RELEVANCE" : c.similarity>0.4 ? "MEDIUM" : "LOW"}
                  </div>
                  <button onClick={()=>setExpanded(expanded===c.chunk_id ? null : c.chunk_id)} className="text-[10px] font-mono border border-[#262626] rounded-lg px-3 py-1 hover:border-white">
                    {expanded===c.chunk_id ? "COLLAPSE" : "EXPAND"}
                  </button>
                </div>
              </div>

              <div className="mt-4">
                <div className="text-[10px] font-mono text-zinc-500 mb-2">WHY WAS THIS RETRIEVED?</div>
                <div className="flex gap-2">
                  <div className="text-[10px] font-mono bg-[#1a1a1a] border border-[#262626] rounded-full px-2 py-1">Similarity: {c.similarity.toFixed(4)}</div>
                  <div className="text-[10px] font-mono bg-[#1a1a1a] border border-[#262626] rounded-full px-2 py-1">Document: {c.document}</div>
                  <div className="text-[10px] font-mono bg-[#1a1a1a] border border-[#262626] rounded-full px-2 py-1">Page: {c.page}</div>
                </div>
              </div>

              <div className={`mt-4 bg-[#0a0a0a] border border-[#262626] rounded-xl p-4 text-sm leading-relaxed whitespace-pre-wrap ${expanded===c.chunk_id ? "" : "line-clamp-4"}`}>
                {c.text}
              </div>
            </div>
          ))}
        </div>
      )}

      {chunks.length===0 && (
        <div className="card p-12 text-center">
          <div className="text-zinc-500 font-mono text-sm">Enter a question and inspect retrieved context. See rank, document, page, similarity, and full text.</div>
        </div>
      )}
    </div>
  )
}
