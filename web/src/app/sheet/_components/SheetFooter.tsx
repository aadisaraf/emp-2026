import { Note, TabCard } from "@/components";
import type { Coverage } from "@/lib/api";
import { TIER_LEGEND } from "@/lib/strings";
import { formatCount, formatPercent } from "@/lib/format";

/* What the sheet leaves out, stated on the sheet. */

export function SheetFooter({ coverage, screeningRule }: {
  coverage: Coverage;
  /** matching/screen.SCREENING_RULE, rendered verbatim. */
  screeningRule: string | null;
}) {
  return (
    <TabCard title="What this sheet leaves out" tone="sunken">
      <Note>
        {screeningRule ??
          "The screening rule could not be read from the API, so it is not reproduced here. It is served by GET /api/v1/sources."}
      </Note>

      <Note>{TIER_LEGEND}</Note>

      <Note>
        Recall code fields parsed: {formatCount(coverage.parsed)} of {formatCount(coverage.total)} (
        {formatPercent(coverage.percent)}). The remaining {formatCount(coverage.unparsed)} carry no
        machine-readable code, so those records are matched on product name alone and their lines
        are held rather than pulled.
      </Note>

      <Note>
        Held lines are on this sheet on purpose, in the same order as pull lines. Nothing here was
        cleared automatically, and nothing in this system can be: a clearing is written by a person
        who names themselves, and the line stays afterwards.
      </Note>
    </TabCard>
  );
}
