import type { ReactNode } from "react";

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
        <span key={key} className="cites">
          {labels.map((label) =>
            props.validLabels.has(label) ? (
              <button
                key={label}
                type="button"
                className="cite"
                onClick={() => props.onCite?.(label)}
                aria-label={`Show source ${label.slice(1)}`}
              >
                {label.slice(1)}
              </button>
            ) : (
              <span key={label} className="cite invalid" title="This marker does not match any passage given to the model.">
                {label.slice(1)}?
              </span>
            ),
          )}
        </span>,
      );
    } else if (match[2]) {
      out.push(<strong key={key}>{inline(match[2], props, key)}</strong>);
    } else if (match[3]) {
      out.push(<code key={key}>{match[3]}</code>);
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
      <p key={key} className="inference">
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
      blocks.push(list.ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>);
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
    <div className="answer">
      {blocks}
      {props.streaming && <span className="typing-caret" aria-hidden="true" />}
    </div>
  );
}
