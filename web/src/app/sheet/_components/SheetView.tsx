import { PageHeader, StatusBadge } from "@/components";
import type { SheetResponse } from "@/lib/api";
import { PAGE_TITLES, pullSheetSubtitle } from "@/lib/strings";
import { SheetFooter } from "./SheetFooter";
import { SheetHeaderBlock } from "./SheetHeaderBlock";
import { PastRunBanner, RunWithoutLines, ZeroMatchNotice } from "./SheetNotices";
import { SheetSurface } from "./SheetSurface";
import { StorageSections } from "./StorageSections";
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

  return (
    <>
      <PageHeader
        title={PAGE_TITLES.pullSheet}
        context={pullSheetSubtitle(run.id, run.business_date)}
        actions={refused ? <StatusBadge value={run.status} /> : undefined}
      />

      <div className={styles.stack}>
        {sheet.is_current ? null : (
          <PastRunBanner
            header={header}
            decidedBefore={sheet.decided_before}
            currentRunId={currentRunId}
          />
        )}

        {/*
          Print-only. On screen the corpus and its provenance are already in
          the status line above, and the counts are already in the stat rail.
        */}
        <SheetHeaderBlock header={header} />

        {refused ? <RunWithoutLines run={run} showCurrentLink={!sheet.is_current} /> : null}

        {!refused && header.counts.total === 0 ? <ZeroMatchNotice header={header} /> : null}

        {hasLines ? (
          <SheetSurface>
            <StorageSections sections={sheet.sections} />
          </SheetSurface>
        ) : null}

        <SheetFooter
          coverage={header.coverage}
          screeningRule={screeningRule}
          runId={sheet.is_current ? run.id : null}
          servesMealProgram={header.location.serves_meal_program}
        />
      </div>
    </>
  );
}
