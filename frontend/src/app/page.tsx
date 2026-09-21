"use client"
import { motion } from "framer-motion"
import Link from "next/link"
import { KCard } from "@/components/MetricCard"
import { useState, useEffect } from "react"
import { API_URL } from "@/lib/utils"

export default function LandingPage() {
  const [stats, setStats] = useState<any>(null)

  useEffect(() => {
    fetch(`${API_URL}/health`).then(r=>r.json()).then(setStats).catch(()=>{})
  }, [])

  return (
    <div className="space-y-12">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-[#262626] bg-[#141414] p-8 md:p-16">
        <div className="absolute inset-0 bg-gradient-to-br from-[#ff3b30]/10 via-transparent to-transparent" />
        <div className="relative">
          <div className="inline-flex items-center gap-2 border border-[#262626] rounded-full px-3 py-1 text-[10px] font-mono tracking-widest text-zinc-400 mb-6">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            RESEARCH MODE • EXPERIMENTAL VALIDITY • K IS THE ONLY VARIABLE
          </div>
          
          <motion.h1 initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} className="text-5xl md:text-8xl font-mono font-black tracking-tighter leading-[0.9]">
            CONTEXT<br/>LENS
          </motion.h1>
          
          <motion.p initial={{opacity:0}} animate={{opacity:1}} transition={{delay:0.2}} className="mt-6 text-xl md:text-2xl font-mono text-zinc-300 max-w-3xl">
            Does more context make AI smarter?
          </motion.p>

          <motion.p initial={{opacity:0}} animate={{opacity:1}} transition={{delay:0.3}} className="mt-4 text-sm text-zinc-400 max-w-2xl leading-relaxed">
            We investigate how retrieval depth changes the quality, faithfulness and latency of Retrieval-Augmented Generation. Same documents, same chunks, same embedding model, same LLM — only K changes. <span className="text-white font-mono">K ∈ {'{1,3,5,10}'}</span>
          </motion.p>

          <div className="mt-10 flex flex-wrap gap-3">
            <Link href="/experiment" className="bg-white text-black px-6 py-3 rounded-xl font-mono font-bold text-xs tracking-widest hover:bg-zinc-200 transition-colors">
              RUN AN EXPERIMENT →
            </Link>
            <Link href="/dashboard" className="border border-[#262626] px-6 py-3 rounded-xl font-mono font-bold text-xs tracking-widest hover:border-white transition-colors">
              VIEW RESEARCH DASHBOARD
            </Link>
          </div>

          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-3 max-w-3xl">
            {[1,3,5,10].map(k => (
              <KCard key={k} k={k} />
            ))}
          </div>
        </div>
      </div>

      {/* Metrics overview */}
      <div className="grid md:grid-cols-4 gap-4">
        <div className="card p-6">
          <div className="text-[10px] font-mono text-zinc-500 tracking-widest">RESEARCH QUESTION</div>
          <div className="mt-3 text-sm leading-relaxed text-zinc-300">Does increasing retrieved chunks always improve answer quality? We measure accuracy, relevance, hallucination, latency.</div>
        </div>
        <div className="card p-6">
          <div className="text-[10px] font-mono text-zinc-500 tracking-widest">DATASET</div>
          <div className="mt-3 text-sm text-zinc-300">IIT Roorkee PG Brochure (25p) + PhD Brochure (37p). 50 questions: 15 factual, 10 procedural, 10 eligibility, 5 conditional, 5 numerical, 5 multi-part.</div>
        </div>
        <div className="card p-6">
          <div className="text-[10px] font-mono text-zinc-500 tracking-widest">EXPERIMENTAL DESIGN</div>
          <div className="mt-3 text-sm text-zinc-300">Paired design: same 50 questions tested at K=1,3,5,10 → 200 runs. Constant: docs, chunks, embedding, LLM, prompt.</div>
        </div>
        <div className="card p-6 border-[#ff3b30]/20">
          <div className="text-[10px] font-mono text-[#ff3b30] tracking-widest">SYSTEM STATUS</div>
          <div className="mt-3 space-y-1 text-xs font-mono">
            <div>FAISS: {stats?.faiss_index_size ?? '—'} vectors</div>
            <div>Model: {stats?.embedding_model?.split('/').pop() ?? '—'}</div>
            <div>LLM: {stats?.llm_provider ?? '—'}</div>
            <div>Benchmark: {stats?.benchmark_loaded ? 'Loaded ✓' : 'Missing'}</div>
          </div>
        </div>
      </div>

      {/* Architecture mini */}
      <div className="card p-6">
        <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-6">RAG ARCHITECTURE • RESEARCH TOOL</div>
        <div className="grid md:grid-cols-6 gap-2 text-center">
          {[
            ["PDFs","2 docs, 62 pages"],
            ["Pages","JSONL, cleaned"],
            ["Chunks","500w, 80 overlap"],
            ["Embeddings","MiniLM-L6-v2, FAISS"],
            ["Retrieval","Top-K, cosine"],
            ["Generation","Cited, faithful"]
          ].map(([title, desc], i) => (
            <div key={title} className="border border-[#262626] rounded-xl p-4 bg-[#0a0a0a]">
              <div className="text-[10px] font-mono text-zinc-500">{i+1}</div>
              <div className="mt-2 text-xs font-mono font-bold">{title}</div>
              <div className="mt-1 text-[10px] text-zinc-500">{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
