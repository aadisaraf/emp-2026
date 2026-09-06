import type { HoldLine, HoldRecordResponse } from "@/lib/api";
import { attempt, getHoldRecord } from "@/lib/api";
import {
  ClearedMark,
  DataTable,
  NotRecorded,
  StatusBadge,
  type Column,
} from "@/components";
import { formatCount, formatQuantity } from "@/lib/format";
import { PAGE_TITLES } from "@/lib/strings";
import {
  ArtifactUnavailable,
  DocumentSheet,
  RecallRefs,
  SignatureBlock,
  SourceList,
  runParam,
  type ArtifactSearchParams,
} from "../_components";
import styles from "../_components/document.module.css";
import { PRINT_LABEL } from "@/lib/nav";

/* The hold and destruction record. */

export const dynamic = "force-dynamic";

export default async function HoldRecordPage({
  searchParams,
}: {
  searchParams?: Promise<ArtifactSearchParams>;
}) {
  const params = searchParams ? await searchParams : undefined;
  const result = await attempt(getHoldRecord(runParam(params)));

  if (!result.ok) {
    return <ArtifactUnavailable title={PAGE_TITLES.holdRecord} failure={result.error} />;
  }

  const record = result.data;
  const total = record.pull_count + record.held_count;

  return (
    <DocumentSheet
      title="Hold and Destruction Record"
      printLabel={PRINT_LABEL["/artifacts/hold"]}
      intro={
        <>
          Custody of what came off the shelf. Print it, work it case by case, and sign
          the blank fields by hand. The counts here are inventory lines, one row per
          case, not the pull sheet&apos;s match lines.
        </>
      }
      location={record.location}
      runId={record.run_id}
      generatedAt={record.generated_at}
      run={record.header.run}
      header={record.header}
      footer={<SourceList sources={record.sources} />}
    >
      <p className={styles.lead}>
        <span className={styles.figure}>{formatCount(record.pull_count)}</span> line
        {record.pull_count === 1 ? "" : "s"} to remove from service.{" "}
        <span className={styles.figure}>{formatCount(record.held_count)}</span> held
        undecided and on the sheet. Both are inventory lines, one row per case in
        the kitchen.
      </p>
      <p className={styles.leadSecond}>
        The pull sheet counts match lines instead, {record.header.counts.pull_count} PULL
        and {record.header.counts.held_count} HELD, because a case named by more than one
        recall notice is more than one line there and one line here. A held case stays on
        this record: it is off the menu while a person decides, and leaving it off would
        put a case in the freezer that no paperwork accounts for.
      </p>
      <p className={styles.caveat}>{record.quantity_caveat}</p>

      <section className={styles.section}>
        <h2 className={styles.sectionHead}>
          Items removed from service or held ({formatCount(total)})
        </h2>
        <p className={styles.sectionNote}>
          Order follows the record as the run produced it. Tick the last column as each
          case is physically found and moved. Every notice naming a case is printed, and a
          notice the agency has since terminated or amended keeps its place: a withdrawn
          notice does not un-recall a case that is already in the freezer.
        </p>
        <div className={styles.sectionTable}>
          <DataTable<HoldLine>
            columns={COLUMNS}
            rows={record.lines}
            rowKey={(line) => line.id}
            caption="Every inventory line held or pulled on this run"
            empty={<EmptyRecord record={record} />}
          />
        </div>
      </section>

      <SignatureBlock
        heading="To be completed by hand"
        note="Every field below is blank and stays blank. This system records what was found on the shelf. It does not record who handled it, and it never fills a name or a date in for you."
        fields={record.signature_fields}
      />
    </DocumentSheet>
  );
}

function EmptyRecord({ record }: { record: HoldRecordResponse }) {
  return (
    <>
      No inventory line on run #{record.run_id} matched a recall, so there is nothing to
      hold. The comparison ran and produced no line. This page is the record that it ran.
    </>
  );
}

const COLUMNS: Column<HoldLine>[] = [
  {
    key: "status",
    header: "Status",
    width: "78px",
    render: (line) => (
      <StatusBadge
        value={line.status}
        title={
          line.status === "PULL"
            ? "At least one recall against this case is strong enough to pull"
            : "Held for a person to look at"
        }
      />
    ),
  },
  {
    key: "item",
    header: "Item",
    groupEdge: true,
    render: (line) => {
      // A clearing is an audit row, never a third status and never a removal.
      // The case keeps its place on the custody record and carries the fact.
      const cleared = line.recalls.reduce((sum, recall) => sum + recall.cleared_count, 0);
      return (
        <>
          <span className={styles.item}>{line.raw_description}</span>
          {line.pack_size ? <span className={styles.fine}>{line.pack_size}</span> : null}
          {cleared > 0 ? (
            <span className={styles.markLine}>
              <ClearedMark count={cleared} />
            </span>
          ) : null}
        </>
      );
    },
  },
  {
    key: "quantity",
    header: "Qty",
    variant: "measure",
    width: "82px",
    render: (line) =>
      formatQuantity(line.quantity, line.unit) ?? <NotRecorded />,
  },
  {
    key: "storage",
    header: "Storage location",
    width: "116px",
    render: (line) => line.storage_location ?? <NotRecorded />,
  },
  {
    key: "lot",
    header: "Lot",
    variant: "identifier",
    width: "96px",
    render: (line) => line.lot_code ?? <NotRecorded />,
  },
  {
    key: "supplier",
    header: "Supplier",
    width: "150px",
    render: (line) => {
      const maker = line.brand ?? line.manufacturer;
      return (
        <>
          {maker ?? <NotRecorded />}
          {line.vendor_name ? (
            <span className={styles.fine}>
              via {line.vendor_name}
              {line.vendor_item_code ? ` ${line.vendor_item_code}` : ""}
            </span>
          ) : null}
        </>
      );
    },
  },
  {
    key: "recalls",
    header: "Recall notices",
    width: "300px",
    groupEdge: true,
    render: (line) => <RecallRefs refs={line.recalls} />,
  },
  {
    key: "counted",
    header: "Found",
    width: "52px",
    headerTitle: "Tick when the case is in hand",
    render: () => (
      <span className={styles.checkbox} aria-hidden="true">
        &#9744;
      </span>
    ),
  },
];
