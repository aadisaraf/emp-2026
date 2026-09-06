import Link from "next/link";
import type { Coverage } from "@/lib/api";
import { TIER_LEGEND } from "@/lib/strings";
import { formatCount, formatPercent } from "@/lib/format";
import styles from "./sheet.module.css";

export interface SheetFooterProps {
  coverage: Coverage;
  /** matching/screen.SCREENING_RULE, rendered verbatim. */
  screeningRule: string | null;
  /** Links to the printable artifacts, offered only from the current sheet. */
  runId: number | null;
  servesMealProgram: boolean;
}

/*
  What the sheet leaves out, stated on the sheet.

  The screening rule is the answer to the question a health inspector asks
  second: not "what did you find" but "what did you never look at". It comes
  from the matcher itself and is printed word for word, because a paraphrase
  would be a claim about the system's behaviour that the system has not made.

  The parser coverage sentence is the same argument in numbers: a recall record
  with no machine-readable code can only be matched on the wording of a product
  name, and a line matched that way is held rather than pulled.
*/

export function SheetFooter({
  coverage,
  screeningRule,
  runId,
  servesMealProgram,
}: SheetFooterProps) {
  return (
    <footer className={styles.footer}>
      <p className={styles.footerItem}>
        <span className={styles.footerLead}>What this sheet leaves out.</span>{" "}
        {screeningRule ?? (
          <span>
            The screening rule could not be read from the API, so it is not reproduced here.
            It is served by GET /api/v1/sources.
          </span>
        )}
      </p>

      <p className={styles.footerItem}>
        <span className={styles.footerLead}>How a line becomes PULL or HELD.</span> {TIER_LEGEND}
      </p>

      <p className={styles.footerItem}>
        <span className={styles.footerLead}>Recall code fields parsed.</span>{" "}
        {formatCount(coverage.parsed)} of {formatCount(coverage.total)} (
        {formatPercent(coverage.percent)}). The remaining {formatCount(coverage.unparsed)} carry no
        machine-readable code, so those records are matched on product name alone and their lines
        are held rather than pulled.
      </p>

      <p className={styles.footerItem}>
        <span className={styles.footerLead}>Held lines.</span> Held lines are on this sheet on
        purpose, interleaved in the same order as pull lines. Nothing on this sheet was cleared
        automatically, and nothing in this system can be: a clearing is written by a person who
        names themselves, and the line stays here afterwards.
      </p>

      {runId !== null ? (
        <p className={`${styles.artifactLinks} no-print`}>
          <Link href={`/artifacts/hold?run=${runId}`}>Hold record</Link>
          <Link href={`/artifacts/credit-claim?run=${runId}`}>Credit claim</Link>
          {servesMealProgram ? (
            <Link href={`/artifacts/state-report?run=${runId}`}>State report</Link>
          ) : null}
          {servesMealProgram ? <Link href="/impact">Menu impact</Link> : null}
        </p>
      ) : null}
    </footer>
  );
}
