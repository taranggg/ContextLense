"use client"
import { useEffect, useState } from "react"
import { API_URL } from "@/lib/utils"

export default function FailuresPage() {
  const [failures, setFailures] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_URL}/api/failure-cases`).then(r=>r.json()).then(d=>{
      setFailures(d.failure_cases || [])
      setLoading(false)
    }).catch(()=>setLoading(false))
  }, [])

  if (loading) return <div className="card p-12 text-center font-mono text-zinc-500">Loading failure cases...</div>

  if (failures.length===0) {
    return (
      <div className="card p-12 text-center">
        <div className="text-4xl mb-4">🔍</div>
        <div className="font-mono font-bold">FAILURE CASES • NO DATA YET</div>
        <div className="text-sm text-zinc-500 mt-2">Run full experiment to auto-identify failure cases: irrelevant context, missed passages, contradictory chunks, latency, ignored context, unsupported claims, duplicates.</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="text-[10px] font-mono tracking-widest text-zinc-500">FAILURE CASE ANALYSIS • EVIDENCE-BASED</div>
        <div className="text-xl font-mono font-bold mt-2">Interesting Failure Cases Identified Automatically</div>
        <div className="text-xs text-zinc-400 mt-1">{failures.length} cases • Do not invent explanations unsupported by data</div>
      </div>

      <div className="grid gap-4">
        {failures.map((fc, idx)=>(
          <div key={idx} className="card p-6 border-l-2 border-l-[#ff3b30]">
            <div className="flex justify-between items-start">
              <div>
                <div className="text-[10px] font-mono px-2 py-1 bg-[#ff3b30]/10 border border-[#ff3b30]/20 rounded-full inline-block text-[#ff3b30]">{fc.failure_type}</div>
                <div className="mt-3 text-sm font-mono font-bold">{fc.question_id} • {fc.question}</div>
                <div className="text-[11px] text-zinc-500 mt-1 font-mono">K={fc.k} • Observed: {fc.observed}</div>
              </div>
              <div className="text-[9px] font-mono text-zinc-600">CASE #{idx+1}</div>
            </div>

            <div className="mt-4 grid md:grid-cols-2 gap-4">
              <div className="bg-[#0a0a0a] border border-[#262626] rounded-xl p-3">
                <div className="text-[10px] font-mono text-zinc-500 mb-2">EXPLANATION (EVIDENCE-BASED)</div>
                <div className="text-xs text-zinc-300 leading-relaxed">{fc.explanation}</div>
              </div>
              <div className="bg-[#0a0a0a] border border-[#262626] rounded-xl p-3">
                <div className="text-[10px] font-mono text-zinc-500 mb-2">METRICS</div>
                <pre className="text-[10px] font-mono text-zinc-400 overflow-x-auto">{JSON.stringify(fc.metrics, null, 2)}</pre>
              </div>
            </div>

            {fc.answer && (
              <div className="mt-4 bg-[#0a0a0a] border border-[#262626] rounded-xl p-3">
                <div className="text-[10px] font-mono text-zinc-500 mb-2">GENERATED ANSWER</div>
                <div className="text-xs text-zinc-300">{fc.answer}</div>
              </div>
            )}

            {fc.retrieved_context && (
              <div className="mt-4">
                <div className="text-[10px] font-mono text-zinc-500 mb-2">RETRIEVED CONTEXT (SNIPPETS)</div>
                <div className="space-y-2">
                  {fc.retrieved_context.slice(0,3).map((ctx:string, i:number)=>(
                    <div key={i} className="text-[11px] text-zinc-400 border border-[#262626] rounded-lg p-2 bg-[#0a0a0a]">{ctx}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
