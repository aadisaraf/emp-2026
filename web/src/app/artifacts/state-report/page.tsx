import type { ReportField, ReportSection } from "@/lib/api";
import { attempt, getStateReport } from "@/lib/api";
import { DataTable, type Column } from "@/components";
import { formatCount } from "@/lib/format";
import { PAGE_TITLES } from "@/lib/strings";
import {
  ArtifactUnavailable,
  DocumentSheet,
  HumanEntryMark,
  SourceList,
  runParam,
  type ArtifactSearchParams,
} from "../_components";
import styles from "../_components/document.module.css";
import reportStyles from "./report.module.css";
import { PRINT_LABEL } from "@/lib/nav";

/*
  The child nutrition recall report.

  24 fields. 11 come out of the database and carry the table they came from.
  13 cannot, and each of those says REQUIRES HUMAN ENTRY and why: an agreement
  number the state issues, a notification that happened on a telephone, a
  signature.

  Not one field is silently blank. A form that quietly left the 13 empty would
  be the most dangerous artifact in this application, because a director would
  sign it believing it was finished. The marker is the whole product here.

  The layout is modelled on USDA FNS guidance and written by the build team. It
  is not an official state form and the page says so above the fields, not in a
  footnote.
*/

export const dynamic = "force-dynamic";

export default async function StateReportPage({
  searchParams,
}: {
  searchParams?: Promise<ArtifactSearchParams>;
}) {
  const params = searchParams ? await searchParams : undefined;
  const result = await attempt(getStateReport(runParam(params)));

  if (!result.ok) {
    return <ArtifactUnavailable title={PAGE_TITLES.stateReport} failure={result.error} />;
  }

  const report = result.data;
  const columns = fieldColumns(report.human_marker);

  return (
    <DocumentSheet
      title="Child Nutrition Recall Report"
      printLabel={PRINT_LABEL["/artifacts/state-report"]}
      intro={
        <>
          Modelled on USDA FNS recall reporting guidance and hand-authored. Print it,
          complete the marked fields, then transfer the values into your state
          agency&apos;s own form using the structured export at the foot of the page.
        </>
      }
      location={report.location}
      runId={report.run_id}
      generatedAt={report.generated_at}
      run={report.header.run}
      header={report.header}
      footer={
        <SourceList
          sources={report.sources}
          note="The form layout itself is hand-authored. No state agency published it."
        />
      }
    >
      <div className={styles.notes}>
        <p className={styles.note}>
          <span className={styles.noteStrong}>{report.caveat}</span>
        </p>
      </div>

      <p className={styles.lead}>
        <span className={styles.figure}>{formatCount(report.derived_count)}</span> of{" "}
        <span className={styles.figure}>{formatCount(report.fields.length)}</span> fields
        were derived from the database and name the table they came from.{" "}
        <span className={styles.figure}>{formatCount(report.unfilled.length)}</span> could
        not be, and each one is marked {report.human_marker} with the reason it cannot be
        filled here.
      </p>
      <p className={styles.leadSecond}>
        No field on this form is silently blank. A blank box reads as nothing to report;
        a marked box reads as not finished, and on a report a director signs, that is the
        difference that matters.
      </p>

      {report.sections.map((section) => (
        <ReportSectionBlock key={section.section} section={section} columns={columns} />
      ))}

      <section className={styles.section}>
        <h2 className={styles.sectionHead}>Structured export</h2>
        <p className={styles.sectionNote}>
          The same 24 fields as plain text, in order, for copying into your state
          agency&apos;s own form. A field nobody has filled in yet carries{" "}
          {report.human_marker} here too, so a copied block cannot look complete when it
          is not.
        </p>
        <pre className={reportStyles.export}>
          {report.export
            .map((entry) => `${entry.label.padEnd(46, " ")}${entry.value}`)
            .join("\n")}
        </pre>
      </section>
    </DocumentSheet>
  );
}

function ReportSectionBlock({
  section,
  columns,
}: {
  section: ReportSection;
  columns: Column<ReportField>[];
}) {
  const unfilled = section.fields.filter((field) => field.kind !== "derived").length;

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionHead}>{section.section}</h2>
      <p className={styles.sectionNote}>
        {formatCount(section.fields.length)} fields.{" "}
        {unfilled === 0
          ? "All derived from the database."
          : `${formatCount(unfilled)} need a person.`}
      </p>
      <div className={styles.sectionTable}>
        <DataTable<ReportField>
          columns={columns}
          rows={section.fields}
          rowKey={(field) => field.label}
          caption={`${section.section} fields`}
          rowClassName={(field) =>
            field.kind === "derived" ? undefined : reportStyles.unfilledRow
          }
        />
      </div>
    </section>
  );
}

/**
 * Three columns and no fourth. The field, what is in it, and where that came
 * from or why it is empty. The third column is the one that makes the document
 * checkable: every value points at a table, and every gap points at a reason.
 */
function fieldColumns(marker: string): Column<ReportField>[] {
  return [
    {
      key: "label",
      header: "Field",
      width: "300px",
      render: (field) => <span className={reportStyles.label}>{field.label}</span>,
    },
    {
      key: "value",
      header: "Value",
      groupEdge: true,
      render: (field) =>
        field.kind === "derived" ? (
          <span className={reportStyles.value}>{field.display}</span>
        ) : (
          // kind "blank" is a signature: structurally empty by design, and
          // still marked, because "by design" is not visible to a reader.
          <HumanEntryMark marker={marker} ruled />
        ),
    },
    {
      key: "why",
      header: "Where it came from",
      width: "300px",
      groupEdge: true,
      render: (field) => (
        <span className={reportStyles.why}>
          {field.kind === "derived" ? field.source : field.why}
        </span>
      ),
    },
  ];
}
