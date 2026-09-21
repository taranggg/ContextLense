"use client"
import { motion } from "framer-motion"

const steps = [
  { id: "question", label: "Question", desc: "User query" },
  { id: "embedding", label: "Embedding", desc: "all-MiniLM-L6-v2" },
  { id: "search", label: "Semantic Search", desc: "FAISS IP" },
  { id: "topk", label: "Top-K Retrieval", desc: "K ∈ {1,3,5,10}" },
  { id: "llm", label: "LLM", desc: "OpenAI / Mock" },
  { id: "answer", label: "Answer", desc: "Cited response" },
]

export function PipelineViz({ activeStep }: { activeStep?: string }) {
  return (
    <div className="card p-4">
      <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4">RAG PIPELINE</div>
      <div className="flex flex-col gap-2">
        {steps.map((step, idx) => {
          const isActive = activeStep === step.id
          return (
            <div key={step.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <motion.div
                  animate={{ scale: isActive ? 1.2 : 1 }}
                  className={`w-7 h-7 rounded-full border flex items-center justify-center text-[10px] font-mono ${isActive ? "bg-[#ff3b30] border-[#ff3b30] text-black" : "bg-[#1a1a1a] border-[#262626] text-zinc-400"}`}
                >
                  {idx + 1}
                </motion.div>
                {idx < steps.length - 1 && <div className="w-px h-6 bg-[#262626] mt-1" />}
              </div>
              <div className={`flex-1 pb-6 ${isActive ? "opacity-100" : "opacity-60"}`}>
                <div className="text-xs font-mono font-bold text-white">{step.label}</div>
                <div className="text-[10px] font-mono text-zinc-500">{step.desc}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
