import { Fragment, type ReactNode } from "react";
import styles from "./highlight.module.css";

/* The highlight. */

const JOINER = " + ";

/** The verbatim parts of a stored trigger. Never trimmed, never re-cased. */
export function triggerParts(trigger: string | null | undefined): string[] {
  if (!trigger) return [];
  const parts = trigger.includes(JOINER) ? trigger.split(JOINER) : [trigger];
  return parts.filter((part) => part.length > 0);
}

type Range = [number, number];

/** First non-overlapping occurrence of each part, in reading order. */
function ranges(text: string, parts: string[]): Range[] {
  const found: Range[] = [];
  for (const part of parts) {
    let from = 0;
    for (;;) {
      const at = text.indexOf(part, from);
      if (at === -1) break;
      const end = at + part.length;
      if (!found.some(([start, stop]) => at < stop && start < end)) {
        found.push([at, end]);
        break;
      }
      from = at + 1;
    }
  }
  return found.sort((a, b) => a[0] - b[0]);
}

/** Which parts appear verbatim in this text. Used to report the ones that do not. */
export function partsIn(text: string | null | undefined, parts: string[]): string[] {
  if (!text) return [];
  return parts.filter((part) => text.includes(part));
}

export interface HighlightedProps {
  text: string;
  parts: string[];
}

/**
  The stored text with the stored trigger marked in place. The mark carries a
  1px rule under it as well as the tint, so it survives a grayscale printout
*/
export function Highlighted({ text, parts }: HighlightedProps) {
  const marks = parts.length > 0 ? ranges(text, parts) : [];
  if (marks.length === 0) return <>{text}</>;

  const out: ReactNode[] = [];
  let cursor = 0;
  marks.forEach(([start, end], index) => {
    if (start > cursor) {
      out.push(<Fragment key={`plain-${index}`}>{text.slice(cursor, start)}</Fragment>);
    }
    out.push(
      <mark className={styles.hit} key={`hit-${index}`}>
        {text.slice(start, end)}
      </mark>,
    );
    cursor = end;
  });
  if (cursor < text.length) out.push(<Fragment key="tail">{text.slice(cursor)}</Fragment>);

  return <>{out}</>;
}
