import { Facts, Jumps, PageHero, Pill, Tag } from "@/components";
import type { SheetResponse } from "@/lib/api";
import { formatCount, formatDate } from "@/lib/format";
import { SheetFooter } from "./SheetFooter";
import { SheetHeaderBlock } from "./SheetHeaderBlock";
import { PastRunBanner, RunWithoutLines, ZeroMatchNotice } from "./SheetNotices";
import { SheetSurface } from "./SheetSurface";
import { StorageSections, locationId } from "./StorageSections";
import styles from "./sheet.module.css";

export interface SheetViewProps {
  sheet: SheetResponse;
  /** matching/screen.SCREENING_RULE, or null when the API did not answer. */
  screeningRule: string | null;
  /** The run that is current now, used only to point a past run back at it. */
  currentRunId: number | null;
}

/*
  The pull sheet, for the current run and for any past run. One component, one
  code path: a past run that rendered through different code could quietly
  become a different document.
*/

export function SheetView({ sheet, screeningRule, currentRunId }: SheetViewProps) {
  const { header, run } = sheet;
  const hasLines = sheet.sections.length > 0;
  const refused = run.status !== "ok";
  const counts = header.counts;

  return (
    <>
      <PageHero
        figure={formatCount(counts.pull_count) ?? "0"}
        word={counts.pull_count === 1 ? "line to pull" : "lines to pull"}
        alert={counts.pull_count > 0}
        actions={
          <>
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

      {!refused && counts.total === 0 ? <ZeroMatchNotice header={header} /> : null}

      {hasLines ? (
        <>
          <Jumps
            items={sheet.sections.map((section) => ({
              href: `#${locationId(section.storage_location)}`,
              label: section.storage_location,
              count: formatCount(section.pull + section.held),
            }))}
          />

          <SheetSurface>
            <div className={styles.sections}>
              <StorageSections sections={sheet.sections} />
            </div>
          </SheetSurface>
        </>
      ) : null}

      <SheetFooter coverage={header.coverage} screeningRule={screeningRule} />
    </>
  );
}
