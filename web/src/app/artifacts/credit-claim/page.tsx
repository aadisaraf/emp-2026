import { PAGE_TITLES, PRINT_LABEL } from "@/lib/strings";
import type { ClaimLine, VendorTotal } from "@/lib/api";
import { getCreditClaim } from "@/lib/api";
import { DataTable, NotRecorded, type Column } from "@/components";
import { formatCount, formatMoney, formatQuantity } from "@/lib/format";
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

/* The distributor credit claim. */

export const dynamic = "force-dynamic";

export default async function CreditClaimPage({
  searchParams,
}: {
  searchParams?: Promise<ArtifactSearchParams>;
}) {
  const result = await getCreditClaim(runParam(await searchParams));

  if (!result.ok) {
    return <ArtifactUnavailable title={PAGE_TITLES.creditClaim} failure={result.error} />;
  }

  const claim = result.data;
  const excluded = claim.excluded.length;

  return (
    <DocumentSheet
      title="Distributor Credit Claim"
      printLabel={PRINT_LABEL["/artifacts/credit-claim"]}
      intro={
        <>
          Every pulled line, priced from the export that delivered it. Nothing on this
          claim is estimated, and the lines that could not be priced are named rather
          than dropped.
        </>
      }
      location={claim.location}
      runId={claim.run_id}
      generatedAt={claim.generated_at}
      header={claim.header}
      footer={
        <SourceList
          sources={claim.sources}
          note="The claim layout and the signature block below are hand-authored by the build team. Neither is a distributor's own form."
        />
      }
    >
      <p className={styles.lead}>
        <span className={styles.figure}>{formatCount(claim.counted)}</span> of{" "}
        <span className={styles.figure}>{formatCount(claim.lines.length)}</span> pulled
        lines carry both a quantity and a unit cost and are claimed below.{" "}
        {excluded > 0 ? (
          <>
            <span className={styles.figure}>{formatCount(excluded)}</span> do not. They
            appear in the table with everything the export did carry, and they are outside
            the total.
          </>
        ) : (
          <>Every pulled line carried both, so nothing is outside the total.</>
        )}
      </p>
      <p className={styles.leadSecond}>
        Only PULL lines appear. A held line is undecided, so it is not claimed.
      </p>

      {excluded > 0 ? (
        <div className={styles.notes}>
          <p className={styles.note}>
            <span className={styles.noteStrong}>{claim.exclusion_statement}</span>
          </p>
        </div>
      ) : null}

      <p className={styles.caveat}>{claim.arithmetic}</p>

      <section className={styles.section}>
        <h2 className={styles.sectionHead}>Claimed lines</h2>
        <p className={styles.sectionNote}>
          Extended value is quantity times unit cost, rounded once, by the server. A line
          with no price shows what it does have and says which field was missing.
        </p>
        <div className={styles.sectionTable}>
          <DataTable<ClaimLine>
            columns={LINE_COLUMNS}
            rows={claim.lines}
            rowKey={(line) => line.id}
            caption="Pulled inventory lines and their extended value"
            empty={
              <>
                No line on run #{claim.run_id} is marked PULL, so there is nothing to
                claim. The comparison ran and produced no pulled line.
              </>
            }
          />
        </div>
        <div className={styles.total}>
          <span className={styles.totalLabel}>Total claimed for this run</span>
          <span className={styles.totalValue}>{formatMoney(claim.total)}</span>
        </div>
        <p className={styles.caveat}>
          The total covers the {formatCount(claim.counted)} lines with an extended value.
          {excluded > 0
            ? ` The ${formatCount(excluded)} lines named above are outside it and no price has been estimated for them.`
            : ""}
        </p>
      </section>

      {claim.by_vendor.length > 0 ? (
        <section className={styles.section}>
          <h2 className={styles.sectionHead}>By vendor</h2>
          <p className={styles.sectionNote}>
            The same lines, grouped by who sold them, because the claim is sent per
            distributor. A line whose export named no vendor is grouped under vendor not
            stated rather than assigned to one.
          </p>
          <div className={styles.sectionTable}>
            <DataTable<VendorTotal>
              columns={VENDOR_COLUMNS}
              rows={claim.by_vendor}
              rowKey={(vendor) => vendor.vendor}
              caption="Claimed value by vendor"
            />
          </div>
        </section>
      ) : null}

      <SignatureBlock
        heading="To be completed by hand"
        note="These fields are blank and stay blank. The system priced the lines; a person submits the claim, and the system does not know who that is."
        fields={SUBMISSION_FIELDS}
      />
    </DocumentSheet>
  );
}

/** The part of a printed claim a person signs. Not an API field. */
const SUBMISSION_FIELDS = [
  "Submitted by (print name)",
  "Title",
  "Date submitted",
  "Distributor contact notified",
  "Distributor claim reference",
  "Authorizing signature",
];

const LINE_COLUMNS: Column<ClaimLine>[] = [
  {
    key: "storage",
    header: "Storage location",
    width: "116px",
    render: (line) => line.storage_location ?? <NotRecorded />,
  },
  {
    key: "item",
    header: "Item",
    groupEdge: true,
    render: (line) => (
      <>
        <span className={styles.item}>{line.raw_description}</span>
        {line.pack_size ? <span className={styles.fine}>{line.pack_size}</span> : null}
      </>
    ),
  },
  {
    key: "vendor",
    header: "Vendor item",
    variant: "identifier",
    width: "116px",
    render: (line) => (
      <>
        {line.vendor_item_code ?? <NotRecorded />}
        {line.vendor_name ? <span className={styles.fine}>{line.vendor_name}</span> : null}
      </>
    ),
  },
  {
    key: "lot",
    header: "Lot",
    variant: "identifier",
    width: "96px",
    render: (line) => line.lot_code ?? <NotRecorded />,
  },
  {
    key: "quantity",
    header: "Qty",
    variant: "measure",
    width: "82px",
    groupEdge: true,
    render: (line) => formatQuantity(line.quantity, line.unit) ?? <NotRecorded />,
  },
  {
    key: "unit_cost",
    header: "Unit cost",
    variant: "measure",
    width: "88px",
    render: (line) =>
      line.unit_cost === null ? (
        <NotRecorded word="no price" />
      ) : (
        <span className="money">{formatMoney(line.unit_cost)}</span>
      ),
  },
  {
    key: "extended",
    header: "Extended",
    variant: "measure",
    width: "112px",
    render: (line) =>
      line.extended === null ? (
        <>
          <span className={styles.excluded}>excluded</span>
          <span className={styles.excludedWhy}>{line.excluded_because}</span>
        </>
      ) : (
        <span className="money">{formatMoney(line.extended)}</span>
      ),
  },
  {
    key: "recalls",
    header: "Recall notices",
    width: "210px",
    groupEdge: true,
    render: (line) => <RecallRefs refs={line.recalls} />,
  },
];

const VENDOR_COLUMNS: Column<VendorTotal>[] = [
  { key: "vendor", header: "Vendor", render: (vendor) => vendor.vendor },
  {
    key: "lines",
    header: "Lines",
    variant: "measure",
    width: "88px",
    render: (vendor) => formatCount(vendor.lines),
  },
  {
    key: "excluded",
    header: "Quantity only",
    variant: "measure",
    width: "120px",
    headerTitle: "Lines with no price, excluded from the total",
    render: (vendor) => formatCount(vendor.excluded),
  },
  {
    key: "total",
    header: "Claimed",
    variant: "measure",
    width: "128px",
    render: (vendor) => <span className="money">{formatMoney(vendor.total)}</span>,
  },
];
