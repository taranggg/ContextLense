"use client"
import { useEffect, useState } from "react"
import { API_URL } from "@/lib/utils"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from "recharts"
import { MetricCard } from "@/components/MetricCard"

export default function DashboardPage() {
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_URL}/api/results/summary`).then(r=>r.json()).then(d=>{
      setSummary(d)
      setLoading(false)
    }).catch(()=>{
      setLoading(false)
    })
  }, [])

  if (loading) {
    return <div className="card p-12 text-center font-mono text-zinc-500">Loading research results...</div>
  }

  if (!summary || !summary.has_results) {
    return (
      <div className="space-y-6">
        <div className="card p-12 text-center">
          <div className="text-4xl mb-4">📊</div>
          <div className="font-mono font-bold">RESEARCH DASHBOARD • EXPERIMENT NOT YET RUN</div>
          <div className="text-sm text-zinc-500 mt-2 max-w-xl mx-auto">Run the full 50×4 experiment to populate this dashboard. Required charts: Accuracy vs K, Relevance vs K, Hallucination vs K, Response Time vs K.</div>
          <div className="mt-6 text-[10px] font-mono text-zinc-600">python -m src.experiment --full</div>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            ["Answer Accuracy vs K","Mean accuracy normalized 0-1 across K values"],
            ["Context Relevance vs K","Mean relevance 0-1, measuring if retrieved chunks are actually useful"],
            ["Hallucination Rate vs K","Claim-level SUPPORTED/UNSUPPORTED/CONTRADICTED"],
            ["Response Time vs K","Retrieval + Generation latency"]
          ].map(([title, desc])=>(
            <div key={title} className="card p-6 border-dashed">
              <div className="text-xs font-mono font-bold">{title}</div>
              <div className="text-[11px] text-zinc-500 mt-2">{desc}</div>
              <div className="mt-4 h-32 bg-[#0a0a0a] rounded-xl border border-[#262626] flex items-center justify-center text-[10px] font-mono text-zinc-600">CHART PLACEHOLDER • RUN EXPERIMENT</div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  const aggregated = summary.aggregated || []
  // Transform for charts
  const chartData = aggregated.map((row:any)=>({
    k: row.k,
    accuracy: row.answer_accuracy_mean,
    relevance: row.context_relevance_mean,
    hallucination: row.hallucination_rate_mean,
    response_time: row.total_response_time_ms_mean,
  }))

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="flex justify-between items-start">
          <div>
            <div className="text-[10px] font-mono tracking-widest text-zinc-500">RESEARCH DASHBOARD • OBSERVED RESULTS • NEUTRAL LANGUAGE</div>
            <div className="text-xl font-mono font-bold mt-2">Measured Impact of Retrieval Depth K</div>
            <div className="text-xs text-zinc-400 mt-1">Total runs: {summary.total_runs} • K values: {summary.k_values?.join(", ")} • No automatic winner labeling</div>
          </div>
          <div className="text-[10px] font-mono border border-[#262626] rounded-full px-3 py-1 text-zinc-500">EXPERIMENT COMPLETE ✓</div>
        </div>
      </div>

      <div className="grid md:grid-cols-4 gap-4">
        {aggregated.length>0 && (
          <>
            <MetricCard label="AVG ACCURACY" value={aggregated.reduce((a:any,b:any)=>a+b.answer_accuracy_mean,0)/aggregated.length > 0 ? (aggregated.reduce((a:any,b:any)=>a+b.answer_accuracy_mean,0)/aggregated.length).toFixed(3) : "—"} sub="Normalized 0-1" />
            <MetricCard label="AVG RELEVANCE" value={aggregated.reduce((a:any,b:any)=>a+b.context_relevance_mean,0)/aggregated.length > 0 ? (aggregated.reduce((a:any,b:any)=>a+b.context_relevance_mean,0)/aggregated.length).toFixed(3) : "—"} sub="0-1 scale" />
            <MetricCard label="AVG HALLUCINATION" value={aggregated.reduce((a:any,b:any)=>a+b.hallucination_rate_mean,0)/aggregated.length > 0 ? (aggregated.reduce((a:any,b:any)=>a+b.hallucination_rate_mean,0)/aggregated.length).toFixed(3) : "—"} sub="Lower is better" accent />
            <MetricCard label="AVG RESPONSE TIME" value={aggregated.reduce((a:any,b:any)=>a+b.total_response_time_ms_mean,0)/aggregated.length > 0 ? `${(aggregated.reduce((a:any,b:any)=>a+b.total_response_time_ms_mean,0)/aggregated.length).toFixed(0)}ms` : "—"} sub="Total latency" />
          </>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="card p-6">
          <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4">ANSWER ACCURACY VS K • OBSERVED RESULT</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis dataKey="k" stroke="#a1a1aa" fontSize={10} />
                <YAxis stroke="#a1a1aa" fontSize={10} domain={[0,1]} />
                <Tooltip contentStyle={{background:"#141414", border:"1px solid #262626", fontSize:"10px"}} />
                <Line type="monotone" dataKey="accuracy" stroke="#ffffff" strokeWidth={2} dot={{r:4}} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-6">
          <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4">CONTEXT RELEVANCE VS K • MEASURED CHANGE</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis dataKey="k" stroke="#a1a1aa" fontSize={10} />
                <YAxis stroke="#a1a1aa" fontSize={10} domain={[0,1]} />
                <Tooltip contentStyle={{background:"#141414", border:"1px solid #262626"}} />
                <Line type="monotone" dataKey="relevance" stroke="#22c55e" strokeWidth={2} dot={{r:4}} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-6">
          <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4">HALLUCINATION RATE VS K • OBSERVED RESULT</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis dataKey="k" stroke="#a1a1aa" fontSize={10} />
                <YAxis stroke="#a1a1aa" fontSize={10} domain={[0,1]} />
                <Tooltip contentStyle={{background:"#141414", border:"1px solid #262626"}} />
                <Line type="monotone" dataKey="hallucination" stroke="#ff3b30" strokeWidth={2} dot={{r:4}} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-6">
          <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4">RESPONSE TIME VS K • DIFFERENCE FROM K=1</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis dataKey="k" stroke="#a1a1aa" fontSize={10} />
                <YAxis stroke="#a1a1aa" fontSize={10} />
                <Tooltip contentStyle={{background:"#141414", border:"1px solid #262626"}} />
                <Bar dataKey="response_time" fill="#a855f7" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card p-6">
        <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4">COMPARISON TABLE • AGGREGATED BY K</div>
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr className="border-b border-[#262626] text-zinc-500">
                <th className="text-left p-2">K</th>
                <th className="text-left p-2">Accuracy Mean</th>
                <th className="text-left p-2">Relevance Mean</th>
                <th className="text-left p-2">Hallucination Mean</th>
                <th className="text-left p-2">Response Time Mean (ms)</th>
              </tr>
            </thead>
            <tbody>
              {aggregated.map((row:any)=>(
                <tr key={row.k} className="border-b border-[#1a1a1a] hover:bg-[#1a1a1a]">
                  <td className="p-2 font-bold">TOP-{row.k}</td>
                  <td className="p-2">{row.answer_accuracy_mean?.toFixed(3)}</td>
                  <td className="p-2">{row.context_relevance_mean?.toFixed(3)}</td>
                  <td className="p-2">{row.hallucination_rate_mean?.toFixed(3)}</td>
                  <td className="p-2">{row.total_response_time_ms_mean?.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 text-[10px] font-mono text-zinc-500">Note: Do not label one K as "winner" or "best". Use neutral language: Observed result, Measured change, Difference from K=1.</div>
      </div>

      <div className="card p-6">
        <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4">FIGURES • GENERATED FROM EXPERIMENTS</div>
        <div className="grid md:grid-cols-3 gap-3">
          {summary.figures?.map((fig:string)=>(
            <div key={fig} className="border border-[#262626] rounded-xl overflow-hidden bg-[#0a0a0a]">
              <img src={`${API_URL}/figures/${fig}`} alt={fig} className="w-full h-48 object-contain bg-black" />
              <div className="p-2 text-[9px] font-mono text-zinc-500">{fig}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
