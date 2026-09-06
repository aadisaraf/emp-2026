import Link from "next/link";
import type { ClaimLine, CreditClaim, VendorTotal } from "@/lib/api";
import {
  DataTable,
  NotRecorded,
  Panel,
  ProvenanceLabel,
  StatRail,
  type Column,
  type StatRailItem,
} from "@/components";
import { formatCount, formatMoney, formatQuantity } from "@/lib/format";
import { ExcludedMark } from "./ExcludedMark";
import { MONEY } from "./copy";
import styles from "./impact.module.css";

export interface MoneyPanelProps {
  claim: CreditClaim;
  runId: number;
}

/**
 * What the pulls cost, for every deployment.
 *
 * The rule the whole panel is built around: nothing is estimated. Extended
 * value is quantity times unit cost and nothing else, so a line the export did
 * not price has no extended value, is named as excluded, and keeps its
 * quantity. Three of the 27 fixture lines land there. The server's own
 * exclusion statement names all three and is printed above the table at body
 * size, not tucked into a footnote.
 *
 * Only PULL lines are here. A held line is undecided by definition.
 */
export function MoneyPanel({ claim, runId }: MoneyPanelProps) {
  const items: StatRailItem[] = [
    { label: MONEY.rail.claimable, value: formatMoney(claim.total) },
    { label: MONEY.rail.pulledLines, value: formatCount(claim.lines.length) },
    { label: MONEY.rail.priced, value: formatCount(claim.counted) },
    {
      label: MONEY.rail.excluded,
      value: formatCount(claim.excluded.length),
      title: claim.exclusion_statement,
    },
    { label: MONEY.rail.vendors, value: formatCount(claim.by_vendor.length) },
  ];

  return (
    <Panel
      id="money"
      title={MONEY.title}
      note={claim.arithmetic}
      actions={
        <span className={styles.links}>
          <Link href={`/artifacts/credit-claim?run=${runId}`}>{MONEY.creditClaimLink}</Link>
          <Link href={`/artifacts/hold?run=${runId}`}>{MONEY.holdRecordLink}</Link>
        </span>
      }
      printBlock
    >
      <StatRail items={items} className={styles.rail} />

      <p className={styles.note}>{MONEY.standing}</p>
      <p className={styles.note}>{MONEY.heldNotClaimed}</p>
      <p className={styles.statement}>{claim.exclusion_statement}</p>

      <div className={styles.tableBlock}>
        <h3 className={styles.subhead}>{MONEY.linesTitle}</h3>
        <DataTable<ClaimLine>
          columns={LINE_COLUMNS}
          rows={claim.lines}
          rowKey={(line) => line.id}
          caption={MONEY.linesCaption}
          className={styles.wideMoney}
          scroll
        />
      </div>

      <div className={styles.tableBlock}>
        <h3 className={styles.subhead}>{MONEY.vendorTitle}</h3>
        <DataTable<VendorTotal>
          columns={VENDOR_COLUMNS}
          rows={claim.by_vendor}
          rowKey={(vendor) => vendor.vendor}
          caption={MONEY.vendorCaption}
          scroll
        />
      </div>
    </Panel>
  );
}

/*
  Column order is fixed: the identity of the case first, then the three numbers
  that make the arithmetic, then the codes, then who sold it and what recalled
  it. Measures are right-aligned so magnitudes stack; lot codes and item codes
  are left-aligned mono, because they are names spelled with digits and the
  operator is comparing them against the case in their hands.
*/
const LINE_COLUMNS: Column<ClaimLine>[] = [
  {
    key: "item",
    header: MONEY.columns.item,
    render: (line) => (
      <span className={styles.cellStack}>
        <span className={styles.strong}>{line.raw_description}</span>
        {line.brand || line.pack_size ? (
          <span className={styles.support}>
            {[line.brand, line.pack_size].filter(Boolean).join(" · ")}
          </span>
        ) : null}
        {line.excluded_because ? (
          <span className={styles.reason}>{line.excluded_because}</span>
        ) : null}
      </span>
    ),
  },
  {
    key: "storage",
    header: MONEY.columns.storage,
    width: "120px",
    render: (line) => line.storage_location ?? <NotRecorded />,
  },
  {
    key: "qty",
    header: MONEY.columns.qty,
    variant: "measure",
    width: "84px",
    groupEdge: true,
    render: (line) => formatQuantity(line.quantity, line.unit) ?? <NotRecorded />,
  },
  {
    key: "unit_cost",
    header: MONEY.columns.unitCost,
    variant: "measure",
    width: "88px",
    render: (line) => formatMoney(line.unit_cost) ?? <NotRecorded />,
  },
  {
    key: "extended",
    header: MONEY.columns.extended,
    variant: "measure",
    width: "104px",
    render: (line) =>
      line.extended === null ? (
        <ExcludedMark reason={line.excluded_because} />
      ) : (
        formatMoney(line.extended)
      ),
  },
  {
    key: "lot",
    header: MONEY.columns.lot,
    variant: "identifier",
    width: "104px",
    groupEdge: true,
    render: (line) => line.lot_code ?? <NotRecorded />,
  },
  {
    key: "vendor",
    header: MONEY.columns.vendor,
    width: "136px",
    render: (line) => (
      <span className={styles.cellStack}>
        <span className={styles.primary}>{line.vendor_name ?? <NotRecorded />}</span>
        {line.vendor_item_code ? (
          <span className={`${styles.support} ${styles.identifier}`}>
            {line.vendor_item_code}
          </span>
        ) : null}
      </span>
    ),
  },
  {
    key: "recall",
    header: MONEY.columns.recall,
    width: "250px",
    render: (line) => (
      <span className={styles.list}>
        {line.recalls.map((recall) => (
          <span className={styles.listItem} key={recall.source_record_id}>
            <span className={styles.primary}>{recall.recalling_firm ?? <NotRecorded />}</span>
            <span className={styles.support}>
              <span className={styles.identifier}>
                {recall.source} {recall.source_record_id}
              </span>{" "}
              <ProvenanceLabel
                provenance={recall.source_provenance}
                label={recall.source_provenance_label}
              />
            </span>
          </span>
        ))}
      </span>
    ),
  },
];

const VENDOR_COLUMNS: Column<VendorTotal>[] = [
  { key: "vendor", header: MONEY.columns.vendor, render: (vendor) => vendor.vendor },
  {
    key: "lines",
    header: MONEY.columns.lines,
    variant: "measure",
    width: "92px",
    groupEdge: true,
    render: (vendor) => formatCount(vendor.lines),
  },
  {
    key: "excluded",
    header: MONEY.columns.excludedShort,
    variant: "measure",
    width: "112px",
    render: (vendor) => formatCount(vendor.excluded),
  },
  {
    key: "total",
    header: MONEY.columns.total,
    variant: "measure",
    width: "128px",
    render: (vendor) => formatMoney(vendor.total),
  },
];
