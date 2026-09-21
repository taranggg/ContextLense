"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { motion } from "framer-motion"
import { useEffect, useState } from "react"
import { API_URL } from "@/lib/utils"

const navItems = [
  { href: "/", label: "Overview" },
  { href: "/experiment", label: "Experiment Lab" },
  { href: "/inspector", label: "Context Inspector" },
  { href: "/dashboard", label: "Research Dashboard" },
  { href: "/failures", label: "Failure Cases" },
  { href: "/methodology", label: "Methodology" },
  { href: "/about", label: "About" },
]

export function Navbar() {
  const pathname = usePathname()
  const [apiStatus, setApiStatus] = useState<"online"|"offline"|"checking">("checking")

  useEffect(() => {
    fetch(`${API_URL}/health`).then(r => {
      if (r.ok) setApiStatus("online")
      else setApiStatus("offline")
    }).catch(() => setApiStatus("offline"))
  }, [])

  return (
    <nav className="sticky top-0 z-50 border-b border-[#262626] bg-[#0a0a0a]/80 backdrop-blur-xl">
      <div className="mx-auto max-w-[1600px] px-6 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[#ff3b30] rounded-lg flex items-center justify-center font-mono font-bold text-black text-sm">CL</div>
          <span className="font-mono font-bold tracking-widest text-sm">CONTEXTLENS</span>
          <span className="text-[10px] px-1.5 py-0.5 border border-[#262626] rounded text-zinc-400 ml-2">M.TECH RESEARCH</span>
        </Link>

        <div className="hidden lg:flex items-center gap-1">
          {navItems.map(item => {
            const active = pathname === item.href
            return (
              <Link key={item.href} href={item.href} className={cn("relative px-3 py-1.5 text-xs font-mono tracking-wide rounded-md transition-colors", active ? "text-white" : "text-zinc-400 hover:text-white")}>
                {active && <motion.div layoutId="nav-active" className="absolute inset-0 bg-[#1a1a1a] border border-[#262626] rounded-md" />}
                <span className="relative">{item.label.toUpperCase()}</span>
              </Link>
            )
          })}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-[10px] font-mono">
            <div className={cn("w-2 h-2 rounded-full", apiStatus==="online" ? "bg-green-500" : apiStatus==="offline" ? "bg-red-500" : "bg-yellow-500")} />
            <span className={apiStatus==="online" ? "text-green-400" : apiStatus==="offline" ? "text-red-400" : "text-yellow-400"}>API {apiStatus.toUpperCase()}</span>
          </div>
          <div className="w-px h-4 bg-[#262626]" />
          <div className="text-[10px] font-mono text-zinc-500">K ∈ {'{1,3,5,10}'}</div>
        </div>
      </div>

      {/* Mobile */}
      <div className="lg:hidden border-t border-[#262626] overflow-x-auto">
        <div className="flex gap-1 p-2">
          {navItems.map(item => {
            const active = pathname === item.href
            return (
              <Link key={item.href} href={item.href} className={cn("whitespace-nowrap px-3 py-1.5 text-[10px] font-mono rounded-md", active ? "bg-[#1a1a1a] text-white border border-[#262626]" : "text-zinc-500")}>
                {item.label.toUpperCase()}
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
