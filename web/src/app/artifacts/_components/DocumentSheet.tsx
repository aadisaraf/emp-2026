import type { ReactNode } from "react";
import type { Location, Run, SheetHeader } from "@/lib/api";
import { DefinitionList, PrintButton, type DefinitionItem } from "@/components";
import { formatDateTime, shortDeliveryRef } from "@/lib/format";
import { channelLabel } from "@/lib/strings";
import styles from "./document.module.css";

export interface DocumentSheetProps {
  /** The document's own name, as it reads on the filed copy. */
  title: string;
  /** What the screen says above the paper. Never printed. */
  intro: ReactNode;
  /** The label on the print button. Two or three words. */
  printLabel: string;
  location: Location;
  runId: number;
  generatedAt: string;
  /** The run this document describes, for the business date and the delivery. */
  run?: Run | null;
  /** Drives the past-run and stale-corpus notes. */
  header?: SheetHeader | null;
  /** The sources block, built by SourceList. */
  footer?: ReactNode;
  children: ReactNode;
}

/** The paper frame the three artifacts share. */
export function DocumentSheet({
  title,
  intro,
  printLabel,
  location,
  runId,
  generatedAt,
  run,
  header,
  footer,
  children,
}: DocumentSheetProps) {
  const stamp: DefinitionItem[] = [
    { term: "Inventory run", value: `#${runId}` },
  ];

  if (run) {
    stamp.push({ term: "Business date", value: run.business_date });
    stamp.push({
      term: "Delivery",
      value: shortDeliveryRef(run.delivery_ref) ?? "no delivery reference",
      hint: channelLabel(run.channel),
    });
  }

  stamp.push({
    term: "Generated",
    value: formatDateTime(generatedAt) ?? generatedAt,
    hint: location.timezone_name,
  });

  const pastRun = header ? !header.is_current : false;
  const stale = header?.stale ?? false;

  return (
    <>
      <div className={styles.toolbar}>
        <div className={styles.toolbarText}>{intro}</div>
        <div className={styles.toolbarActions}>
          <PrintButton label={printLabel} variant="primary" />
        </div>
      </div>

      <article className={styles.sheet}>
        <header className={styles.docHead}>
          <div className={styles.docHeadMain}>
            <h1 className={styles.docTitle}>{title}</h1>
            <p className={styles.issuer}>
              <span className={styles.issuerName}>{location.name}</span>
              <br />
              {location.operator}
              <br />
              {location.address}
              <br />
              {location.contact}
            </p>
          </div>
          <DefinitionList items={stamp} className={styles.stamp} />
        </header>

        {pastRun || stale ? (
          <div className={styles.notes}>
            {pastRun && header ? (
              <p className={styles.note}>
                <span className={styles.noteStrong}>
                  This document is built from run #{header.run.id} of{" "}
                  {header.run.business_date}, which is not the current run.
                </span>{" "}
                It is shown exactly as it stood, against the recall data it was matched
                against that morning.
              </p>
            ) : null}
            {stale ? (
              <p className={styles.note}>
                <span className={styles.noteStrong}>
                  The recall corpus is older than 24 hours.
                </span>{" "}
                Every line below still stands. Staleness changes this notice and nothing
                else on the page.
              </p>
            ) : null}
          </div>
        ) : null}

        {children}

        {footer}
      </article>
    </>
  );
}
