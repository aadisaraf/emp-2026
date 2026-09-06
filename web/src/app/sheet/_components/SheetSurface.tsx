"use client";

import { useCallback, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { MatchPane } from "./MatchPane";
import styles from "./sheet.module.css";

/* The sheet body, plus the detail pane when a line is open. */

export function SheetSurface({ children }: {
  children: ReactNode;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const highlighted = useRef<HTMLTableRowElement | null>(null);

  const clearHighlight = () => {
    if (highlighted.current) {
      highlighted.current.removeAttribute("data-selected");
      highlighted.current = null;
    }
  };

  const onClick = (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement | null;
    const trigger = target?.closest<HTMLElement>("[data-match-id]");
    if (!trigger) return;

    const id = Number(trigger.dataset.matchId);
    if (!Number.isFinite(id)) return;

    clearHighlight();
    const row = trigger.closest("tr");
    if (row) {
      row.setAttribute("data-selected", "true");
      highlighted.current = row;
    }
    setSelected(id);
  };

  const close = useCallback(() => {
    clearHighlight();
    setSelected(null);
  }, []);

  return (
    <div className={styles.surface} data-pane={selected === null ? "closed" : "open"}>
      {/* The interactive elements are the buttons inside; this listens on the
          way up so the table itself can stay server-rendered. */}
      <div className={styles.body} onClick={onClick}>
        {children}
      </div>
      {selected !== null ? (
        <MatchPane key={selected} matchId={selected} onClose={close} />
      ) : null}
    </div>
  );
}
