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
    <figure className="chart-card" style={{ margin: 0 }}>
      <h3>{title}</h3>
      {subtitle && <p>{subtitle}</p>}
      <div className="hbar-chart" role="list">
        {bars.map((bar, i) => {
          const width = bar.value == null ? 0 : Math.max(0, Math.min(1, bar.value / top)) * 100;
          return (
            <div
              key={bar.label}
              role="listitem"
              className="hbar-row"
              tabIndex={0}
              aria-label={`${bar.label}: ${bar.display}${bar.detail ? `, ${bar.detail}` : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
            >
              <span className="hbar-label">{bar.label}</span>
              <span className="hbar-track">
                {bar.value != null && <span className="hbar-fill" style={{ width: `${width}%` }} />}
                <span className="hbar-value" style={{ left: `${width}%` }}>
                  {bar.display}
                </span>
                {active === i && bar.detail && (
                  <span className="hbar-tip" role="tooltip">
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
