export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
}

export function formatPages(pages: number[]): string {
  if (!pages.length) return "";
  if (pages.length === 1) return `p. ${pages[0]}`;
  const contiguous = pages.every((p, i) => i === 0 || p === pages[i - 1] + 1);
  return contiguous ? `pp. ${pages[0]}–${pages[pages.length - 1]}` : `pp. ${pages.join(", ")}`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  const diff = (Date.now() - date.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function pct(value: number | null | undefined, digits = 0): string {
  return value == null ? "—" : `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : value.toFixed(digits);
}

export function plural(n: number, word: string, pluralWord = word + "s"): string {
  return `${n.toLocaleString()} ${n === 1 ? word : pluralWord}`;
}
