import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { useReady } from "../lib/readiness";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { StatusDot } from "./common";
import { cn } from "@/lib/utils";

const LLM_LABEL: Record<string, string> = {
  ready: "Model ready",
  loading: "Loading model",
  not_loaded: "Model idle",
  not_downloaded: "Model not downloaded",
  unavailable: "Model unavailable",
  not_configured: "Model not configured",
  error: "Model error",
};

function ModelStatus() {
  const { readiness, error } = useReady();

  let label = "Connecting…";
  let tone: "ok" | "busy" | "bad" = "busy";
  if (error) {
    label = "Backend offline";
    tone = "bad";
  } else if (readiness) {
    const s = readiness.llm.status;
    label = LLM_LABEL[s] ?? s;
    tone = s === "ready" ? "ok" : s === "loading" || s === "not_loaded" ? "busy" : "bad";
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex h-[30px] items-center gap-2 rounded-md border border-border bg-card px-3 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
        >
          <StatusDot tone={tone} />
          <span className="hidden sm:inline">{label}</span>
          <span className="sr-only">— show system status</span>
        </button>
      </PopoverTrigger>
      <PopoverContent aria-label="System status">
        {error ? (
          <p>{error.message}</p>
        ) : readiness ? (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
            <dt className="text-muted-foreground">Local model</dt>
            <dd>
              <span className="font-mono text-[0.86em]">{readiness.llm.model}</span>
              <div className="text-muted-foreground">
                {readiness.llm.runtime.toUpperCase()} · {LLM_LABEL[readiness.llm.status] ?? readiness.llm.status}
                {readiness.llm.load_time_s != null && ` · loaded in ${readiness.llm.load_time_s}s`}
              </div>
              {readiness.llm.detail && <div className="text-muted-foreground">{readiness.llm.detail}</div>}
            </dd>
            <dt className="text-muted-foreground">Embeddings</dt>
            <dd>
              {readiness.embedding.detail}
              <div className="text-muted-foreground">{readiness.embedding.status.replace("_", " ")}</div>
            </dd>
            <dt className="text-muted-foreground">Storage</dt>
            <dd>{readiness.storage.detail}</dd>
            <dt className="text-muted-foreground">Privacy</dt>
            <dd className="text-muted-foreground">Documents and questions are processed on this machine. No hosted AI service is called.</dd>
          </dl>
        ) : (
          <p className="text-muted-foreground">Checking…</p>
        )}
      </PopoverContent>
    </Popover>
  );
}

function NavItem({ to, end, children }: { to: string; end?: boolean; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground hover:no-underline",
          isActive && "bg-secondary text-foreground",
        )
      }
    >
      {children}
    </NavLink>
  );
}

export function Header() {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-6 border-b border-border bg-background/85 px-6 backdrop-blur-md backdrop-saturate-150">
      <Link to="/" className="font-sans text-[17px] font-semibold tracking-tight text-foreground hover:no-underline" aria-label="ContextLens home">
        ContextLens
      </Link>
      <nav className="flex gap-1" aria-label="Main">
        <NavItem to="/" end>
          Documents
        </NavItem>
        <NavItem to="/research">Research</NavItem>
      </nav>
      <div className="flex-1" />
      <ModelStatus />
    </header>
  );
}
