"use client";

import type { SheetResponse, StatusResponse } from "@/lib/types";
import { useStatusFeed } from "./useStatusFeed";
import { Hero, StageBar } from "./Hero";
import { DocumentsColumn, LinesColumn, LocationCard, RunCard } from "./Columns";
import styles from "./dashboard.module.css";

export interface ArtifactFacts {
  credit: { total: number; counted: number } | null;
  report: { derived: number; toEnter: number } | null;
}

export interface Filters {
  q: string;
  loc: string;
  show: string;
}

export interface TodayBoardProps {
  initial: StatusResponse;
  sheet: SheetResponse | null;
  artifacts: ArtifactFacts;
  filters: Filters;
}

/* The morning screen. One figure, two clocks, three columns. */
export function TodayBoard({ initial, sheet, artifacts, filters }: TodayBoardProps) {
  const { status } = useStatusFeed(initial);
  const run = status.run;

  return (
    <>
      <Hero status={status} />
      {run ? <StageBar run={run} deadlines={status.deadlines} /> : null}

      {run ? (
        <div className={styles.body}>
          <div className={styles.side}>
            <LocationCard location={status.location} />
            <RunCard run={run} corpus={status.corpus} />
          </div>

          <LinesColumn sheet={sheet} filters={filters} />

          <DocumentsColumn
            run={run}
            sheet={sheet}
            artifacts={artifacts}
            servesMealProgram={status.location.serves_meal_program}
            claims={status.location.deployment_type === "restaurant"}
          />
        </div>
      ) : null}
    </>
  );
}
