import { cn } from "@/lib/utils"

interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
  className?: string
  tooltip?: string
}

export function MetricCard({ label, value, sub, accent, className, tooltip }: MetricCardProps) {
  return (
    <div className={cn("card p-4", accent && "border-[#ff3b30]/30", className)}>
      <div className="flex justify-between items-start">
        <div className="text-[10px] font-mono tracking-widest text-zinc-500">{label}</div>
        {tooltip && <div className="text-[9px] text-zinc-600 border border-[#262626] rounded px-1">?</div>}
      </div>
      <div className={cn("mt-2 text-2xl font-mono font-bold tracking-tight", accent ? "text-[#ff3b30]" : "text-white")}>{value}</div>
      {sub && <div className="mt-1 text-[11px] text-zinc-400 font-mono">{sub}</div>}
    </div>
  )
}

export function KCard({ k, active, onClick }: { k: number, active?: boolean, onClick?: () => void }) {
  return (
    <div onClick={onClick} className={cn("card p-4 cursor-pointer transition-all", active ? "border-[#ff3b30] bg-[#1a0a0a]" : "card-hover")}>
      <div className="text-[10px] font-mono text-zinc-500">TOP</div>
      <div className="text-3xl font-mono font-black">{k}</div>
      <div className="text-[10px] font-mono text-zinc-500 mt-1">CHUNKS</div>
    </div>
  )
}
