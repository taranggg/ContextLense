import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Renders the small Markdown subset the model is asked to use (paragraphs,
 * lists, bold, code) and turns [S1]-style markers into citation buttons.
 * Builds React elements only; model output is never injected as HTML.
 */

interface Props {
  text: string;
  validLabels: Set<string>;
  onCite?: (label: string) => void;
  streaming?: boolean;
}

const INLINE_RE = /\[\s*(S\d+(?:\s*[,;]\s*S?\d+)*)\s*\]|\*\*(.+?)\*\*|`([^`]+)`/gi;
const LIST_RE = /^\s*(?:[-*•]|\d+[.)])\s+(.*)$/;
const ORDERED_RE = /^\s*\d+[.)]\s+/;

function inline(text: string, props: Props, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let i = 0;
  for (const match of text.matchAll(INLINE_RE)) {
    const index = match.index ?? 0;
    if (index > last) out.push(text.slice(last, index));
    const key = `${keyPrefix}-${i++}`;
    if (match[1]) {
      const labels = match[1].split(/[,;]/).map((p) => "S" + p.replace(/\D/g, "")).filter((l) => l !== "S");
      out.push(
        <span key={key}>
          {labels.map((label) =>
            props.validLabels.has(label) ? (
              <button
                key={label}
                type="button"
                className="mx-px inline-grid h-[18px] min-w-[18px] place-items-center rounded-[6px] bg-accent px-1.5 text-[11px] font-semibold leading-none text-accent-foreground align-[2px] transition-colors hover:bg-accent/70"
                onClick={() => props.onCite?.(label)}
                aria-label={`Show source ${label.slice(1)}`}
              >
                {label.slice(1)}
              </button>
            ) : (
              <span
                key={label}
                className="mx-px inline-grid h-[18px] min-w-[18px] place-items-center rounded-[6px] bg-secondary px-1.5 text-[11px] font-semibold leading-none text-muted-foreground align-[2px]"
                title="This marker does not match any passage given to the model."
              >
                {label.slice(1)}?
              </span>
            ),
          )}
        </span>,
      );
    } else if (match[2]) {
      out.push(<strong key={key}>{inline(match[2], props, key)}</strong>);
    } else if (match[3]) {
      out.push(
        <code key={key} className="font-mono text-[0.86em]">
          {match[3]}
        </code>,
      );
    }
    last = index + match[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function paragraph(text: string, props: Props, key: string): ReactNode {
  const inference = /^inference:/i.test(text);
  if (inference) {
    return (
      <p key={key} className="text-foreground/80">
        <em>Inference:</em>
        {inline(text.replace(/^inference:/i, ""), props, key)}
      </p>
    );
  }
  return <p key={key}>{inline(text, props, key)}</p>;
}

export function AnswerText(props: Props) {
  const lines = props.text.replace(/\r/g, "").split("\n");
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flushPara = () => {
    if (para.length) blocks.push(paragraph(para.join(" "), props, `p${blocks.length}`));
    para = [];
  };
  const flushList = () => {
    if (list) {
      const key = `l${blocks.length}`;
      const items = list.items.map((item, i) => <li key={i}>{inline(item, props, `${key}-${i}`)}</li>);
      blocks.push(
        list.ordered ? (
          <ol key={key} className="mt-2 list-decimal pl-[22px] [&_li+li]:mt-1">
            {items}
          </ol>
        ) : (
          <ul key={key} className="mt-2 list-disc pl-[22px] [&_li+li]:mt-1">
            {items}
          </ul>
        ),
      );
    }
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const item = LIST_RE.exec(line);
    if (!line.trim()) {
      flushPara();
      flushList();
    } else if (/^#{1,6}\s+/.test(line)) {
      flushPara();
      flushList();
      blocks.push(
        <p key={`h${blocks.length}`}>
          <strong>{inline(line.replace(/^#{1,6}\s+/, ""), props, `h${blocks.length}`)}</strong>
        </p>,
      );
    } else if (item) {
      flushPara();
      const ordered = ORDERED_RE.test(line);
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push(item[1]);
    } else if (list && /^\s{2,}/.test(raw)) {
      list.items[list.items.length - 1] += " " + line.trim(); // continuation of a list item
    } else {
      flushList();
      para.push(line.trim());
    }
  }
  flushPara();
  flushList();

  return (
    <div className={cn("text-[16px] leading-[1.65] [&_p+p]:mt-3 [&_p+ul]:mt-3 [&_p+ol]:mt-3 [&_ul+p]:mt-3 [&_ol+p]:mt-3 [&_strong]:font-semibold")}>
      {blocks}
      {props.streaming && <span className="ml-0.5 inline-block h-[1.05em] w-[7px] translate-y-[2px] animate-caret-blink bg-muted-foreground align-middle" aria-hidden="true" />}
    </div>
  );
}
