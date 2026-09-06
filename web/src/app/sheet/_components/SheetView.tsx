import { Empty, Facts, Jumps, PageHero, Pill, Tag } from "@/components";
import type { SheetResponse } from "@/lib/api";
import { formatCount, formatDate } from "@/lib/format";
import { SheetFooter } from "./SheetFooter";
import { SheetHeaderBlock } from "./SheetHeaderBlock";
import { PastRunBanner, RunWithoutLines, ZeroMatchNotice } from "./SheetNotices";
import { SheetSurface } from "./SheetSurface";
import { StorageSections, locationId } from "./StorageSections";
import type { ClearedFacts } from "./clearedFacts";
import styles from "./sheet.module.css";

export interface SheetViewProps {
  sheet: SheetResponse;
  /** matching/screen.SCREENING_RULE, or null when the API did not answer. */
  screeningRule: string | null;
  cleared: ClearedFacts;
  /** The run that is current now, used only to point a past run back at it. */
  currentRunId: number | null;
  /** The search in the top bar. Empty means the whole sheet. */
  query?: string;
}

/** Every place a person would expect a word they typed to be found. */
function hit(line: { raw_description: string; product_description: string;
                     lot_code: string | null; recalling_firm: string | null;
                     source_record_id: string }, needle: string): boolean {
  return (
    line.raw_description.toLowerCase().includes(needle) ||
    line.product_description.toLowerCase().includes(needle) ||
    (line.lot_code ?? "").toLowerCase().includes(needle) ||
    (line.recalling_firm ?? "").toLowerCase().includes(needle) ||
    line.source_record_id.toLowerCase().includes(needle)
  );
}

/*
  The pull sheet, for the current run and for any past run. One component, one
  code path: a past run that rendered through different code could quietly
  become a different document.
*/

export function SheetView({
  sheet,
  screeningRule,
  cleared,
  currentRunId,
  query = "",
}: SheetViewProps) {
  const { header, run } = sheet;
  const refused = run.status !== "ok";

  /* A search narrows the sheet in place. The counts follow it, so the figure
     on screen is always the count of what is on screen. */
  const needle = query.trim().toLowerCase();
  const sections = needle
    ? sheet.sections
        .map((s) => {
          const lines = s.lines.filter((l) => hit(l, needle));
          return {
            ...s,
            lines,
            pull: lines.filter((l) => l.status === "PULL").length,
            held: lines.filter((l) => l.status === "HELD").length,
            cleared: lines.filter((l) => l.cleared).length,
          };
        })
        .filter((s) => s.lines.length > 0)
    : sheet.sections;

  const hasLines = sections.length > 0;
  const shown = sections.flatMap((s) => s.lines);
  const counts = needle
    ? {
        pull_count: shown.filter((l) => l.status === "PULL").length,
        held_count: shown.filter((l) => l.status === "HELD").length,
        new_count: shown.filter((l) => l.is_new).length,
        total: shown.length,
      }
    : header.counts;

  return (
    <>
      <PageHero
        figure={formatCount(counts.pull_count) ?? "0"}
        word={counts.pull_count === 1 ? "line to pull" : "lines to pull"}
        alert={counts.pull_count > 0}
        actions={
          <>
            {needle ? <Tag tone="attend">matching {query.trim()}</Tag> : null}
            {refused ? <Tag tone="alert">refused</Tag> : <Tag>run #{run.id}</Tag>}
            <Pill href={`/artifacts/hold?run=${run.id}`} tone="primary">
              Hold record
            </Pill>
            <Pill href={`/artifacts/credit-claim?run=${run.id}`}>Credit claim</Pill>
          </>
        }
      />

      <Facts
        items={[
          {
            label: "held",
            value: formatCount(counts.held_count) ?? "0",
            tone: counts.held_count > 0 ? "attend" : "plain",
          },
          { label: "lines", value: formatCount(counts.total) ?? "0" },
          { label: "new", value: formatCount(counts.new_count) ?? "0" },
          { label: "inventory of", value: formatDate(run.business_date) ?? run.business_date },
          {
            label: "corpus",
            value: header.stale ? "stale" : "in force",
            tone: header.stale ? "attend" : "plain",
          },
        ]}
      />

      {sheet.is_current ? null : (
        <PastRunBanner
          header={header}
          decidedBefore={sheet.decided_before}
          currentRunId={currentRunId}
        />
      )}

      {/* Print-only: on screen these facts are already in the row above. */}
      <SheetHeaderBlock header={header} />

      {refused ? <RunWithoutLines run={run} showCurrentLink={!sheet.is_current} /> : null}

      {!refused && !needle && counts.total === 0 ? <ZeroMatchNotice header={header} /> : null}

      {needle && !hasLines ? (
        <Empty>
          No line on this sheet matches &ldquo;{query.trim()}&rdquo;. The sheet still holds{" "}
          {formatCount(header.counts.total)} lines.
        </Empty>
      ) : null}

      {hasLines ? (
        <>
          <Jumps
            items={sections.map((section) => ({
              href: `#${locationId(section.storage_location)}`,
              label: section.storage_location,
              count: formatCount(section.pull + section.held),
            }))}
          />

          <SheetSurface>
            <div className={styles.sections}>
              <StorageSections sections={sections} cleared={cleared} />
            </div>
          </SheetSurface>
        </>
      ) : null}

      <SheetFooter coverage={header.coverage} screeningRule={screeningRule} />
    </>
  );
}
