import { PageHeader, StatusBadge } from "@/components";
import type { SheetResponse } from "@/lib/api";
import { PAGE_TITLES, pullSheetSubtitle } from "@/lib/strings";
import { SheetFooter } from "./SheetFooter";
import { SheetHeaderBlock } from "./SheetHeaderBlock";
import { PastRunBanner, RunWithoutLines, ZeroMatchNotice } from "./SheetNotices";
import { SheetSurface } from "./SheetSurface";
import { StorageSections } from "./StorageSections";
import type { ClearedFacts } from "./clearedFacts";
import styles from "./sheet.module.css";

export interface SheetViewProps {
  sheet: SheetResponse;
  /** matching/screen.SCREENING_RULE, or null when the API did not answer. */
  screeningRule: string | null;
  cleared: ClearedFacts;
  /** The run that is current now, used only to point a past run back at it. */
  currentRunId: number | null;
}

/*
  The pull sheet, for the current run and for any past run. One component, one
  code path: a past run that rendered through different code could quietly
  become a different document.

  The order of the page is the order of the work. What this sheet is, then what
  it says, then what it left out.
*/

export function SheetView({ sheet, screeningRule, cleared, currentRunId }: SheetViewProps) {
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

        {/* Print-only. On screen the corpus and its provenance are already in
            the status line above, and the counts are already in the stat rail;
            repeating them here cost 64px on the one page where rows are the
            point. On paper neither of those exists, so the block is the
            letterhead and the sheet carries its own provenance out of the
            building. */}
        <SheetHeaderBlock header={header} />

        {refused ? <RunWithoutLines run={run} showCurrentLink={!sheet.is_current} /> : null}

        {!refused && header.counts.total === 0 ? <ZeroMatchNotice header={header} /> : null}

        {hasLines ? (
          <div>
            <SheetSurface>
              <StorageSections sections={sheet.sections} cleared={cleared} />
            </SheetSurface>
          </div>
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
