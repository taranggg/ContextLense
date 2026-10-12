import { useState } from "react";

/**
 * Single-series horizontal bar chart: one hue, hairline baseline, value at each bar tip,
 * hover/focus tooltip with the exact value and sample size. Missing values render as "—"
 * (never as zero). Every value is also in the results table.
 */

export interface Bar {
  label: string;
  value: number | null;
  display: string;
  detail?: string;
}

export function BarChart({ title, subtitle, bars, max }: { title: string; subtitle?: string; bars: Bar[]; max?: number }) {
  const [active, setActive] = useState<number | null>(null);
  const top = max ?? Math.max(1e-9, ...bars.map((b) => b.value ?? 0));
  return (
    <figure className="rounded-lg border border-border bg-card p-4.5 pb-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
      <div className="mt-3.5 grid gap-0.5" role="list">
        {bars.map((bar, i) => {
          const width = bar.value == null ? 0 : Math.max(0, Math.min(1, bar.value / top)) * 100;
          return (
            <div
              key={bar.label}
              role="listitem"
              className="grid min-h-[26px] grid-cols-[92px_1fr] items-center gap-2.5 rounded-md"
              tabIndex={0}
              aria-label={`${bar.label}: ${bar.display}${bar.detail ? `, ${bar.detail}` : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
            >
              <span className="whitespace-nowrap text-xs text-foreground/80">{bar.label}</span>
              <span className="relative mr-16 h-[26px] border-l border-border">
                {bar.value != null && (
                  <span
                    className="absolute top-[5px] h-4 rounded-r bg-primary transition-[width] duration-300"
                    style={{ width: `${width}%` }}
                  />
                )}
                <span className="absolute top-0 whitespace-nowrap pl-1.5 text-xs leading-[26px] tabular-nums text-foreground" style={{ left: `${width}%` }}>
                  {bar.display}
                </span>
                {active === i && bar.detail && (
                  <span
                    role="tooltip"
                    className="pointer-events-none absolute bottom-[calc(100%+4px)] left-0 z-10 whitespace-nowrap rounded-md bg-foreground px-2.5 py-2 text-xs leading-snug text-background shadow-md"
                  >
                    <strong>{bar.label}</strong> {bar.display}
                    <br />
                    {bar.detail}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </figure>
  );
}
