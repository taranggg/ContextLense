import "./globals.css"
import { Navbar } from "@/components/Navbar"

export const metadata = {
  title: "ContextLens — Does more context make AI smarter?",
  description: "Investigating impact of retrieval depth on RAG answer quality. Top-1 vs Top-3 vs Top-5 vs Top-10.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0a0a0a] text-white antialiased">
        <Navbar />
        <main className="mx-auto max-w-[1600px] px-4 md:px-6 py-6">
          {children}
        </main>
        <footer className="border-t border-[#262626] mt-12 py-6 text-center">
          <div className="text-[10px] font-mono text-zinc-600 tracking-widest">
            CONTEXTLENS • M.TECH MODERN AI MINI-PROJECT • IIT ROORKEE DOCUMENTS • K ∈ {'{1,3,5,10}'} • RESEARCH TOOL
          </div>
        </footer>
      </body>
    </html>
  )
}
