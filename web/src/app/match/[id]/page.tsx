import Link from "next/link";
import {
  DefinitionList,
  ErrorState,
  NotRecorded,
  PageHeader,
  Panel,
  PrintButton,
  ProvenanceLabel,
  type DefinitionItem,
} from "@/components";
import { attempt, getMatch, isNotFound } from "@/lib/api";
import {
  formatDate,
  formatDateTime,
  formatMoney,
  formatQuantity,
} from "@/lib/format";
import { AgencyRecord } from "../_components/AgencyRecord";
import { Highlighted, partsIn, triggerParts } from "../_components/highlight";
import { LineDecisions } from "../_components/LineDecisions";
import { RecordSide } from "../_components/RecordSide";
import { Verdict } from "../_components/Verdict";
import {
  BACK_TO_RUNS,
  BOTH_RECORDS_NOTE,
  INVENTORY_FIELDS,
  INVENTORY_HEADING,
  INVENTORY_VERBATIM_LABEL,
  IS_NEW_HINT,
  MATCH_ROW_FIELDS,
  MATCH_ROW_HEADING,
  MATCH_TITLE,
  NO_CODE_INFO,
  NO_SCORE,
  RECALL_FIELDS,
  RECALL_HEADING,
  RECALL_VERBATIM_LABEL,
  RECEIVED_AT_HINT,
  SCORE_HINT,
  UNCLASSIFIED,
  VENDOR_ITEM_HINT,
  backToSheet,
  matchContext,
  mergedFrom,
  unpopulatedFields,
} from "../_components/strings";
import styles from "./page.module.css";
import { PRINT_LABEL } from "@/lib/nav";

/*
  One match, in full.

  This is the page that gets opened when somebody asks how the system knows.
  So it shows both stored records side by side, verbatim and complete, with the
  stored trigger marked in place on each side; the tier and the evidence kind
  in words; every decision ever taken about this food and this recall, with the
  person who took it and when; and the two things a person can do next.

  What it deliberately does not have: a bulk action, a dismiss, a mark as false
  positive, a third status, or any number that reads as a confidence. Clearing
  is one line at a time, by a person who names themselves, and the line stays.
*/

export const dynamic = "force-dynamic";

export default async function MatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const matchId = Number(id);

  if (!Number.isInteger(matchId) || matchId <= 0) {
    return (
      <>
        <PageHeader title={MATCH_TITLE} />
        <ErrorState
          heading="This address does not name a match."
          failure={{
            kind: "http",
            status: 404,
            code: "no_match",
            message: `"${id}" is not a match id.`,
            url: "",
          }}
        />
      </>
    );
  }

  const result = await attempt(getMatch(matchId));

  if (!result.ok) {
    return (
      <>
        <PageHeader title={MATCH_TITLE} />
        <ErrorState
          failure={result.error}
          heading={isNotFound(result.error) ? "There is no match with this id." : undefined}
        />
      </>
    );
  }

  const detail = result.data;
  const { match, inventory, recall, header, run } = detail;
  const timeZone = header.location.timezone_name;

  /* The stored trigger, split into its verbatim parts. Compound evidence kinds
     store two parts joined by " + "; searching the whole string would miss. */
  const inventoryParts = triggerParts(match.trigger_inventory_text);
  const recallParts = triggerParts(match.trigger_recall_text);

  /* Which parts appear in the text this side actually shows, so the page can
     say plainly when a stored trigger is nowhere on screen. */
  const inventoryFound = new Set(
    [
      inventory.raw_description,
      inventory.lot_code,
      inventory.gtin,
      inventory.brand,
      inventory.manufacturer,
      inventory.manufacturer_item_code,
    ].flatMap((text) => partsIn(text, inventoryParts)),
  );
  const recallFound = new Set(
    [recall.product_description, recall.code_info, recall.recalling_firm].flatMap((text) =>
      partsIn(text, recallParts),
    ),
  );

  const clearings = detail.decisions.filter((decision) => decision.kind === "clear_match");
  const clearedBy = clearings.length > 0 ? clearings[clearings.length - 1] : null;

  const quantity = formatQuantity(inventory.quantity, inventory.unit);
  const unitCost = formatMoney(inventory.unit_cost);

  const inventoryItems: DefinitionItem[] = [
    {
      term: INVENTORY_FIELDS.storage,
      value: inventory.storage_location ?? <NotRecorded />,
    },
    { term: INVENTORY_FIELDS.quantity, value: quantity ?? <NotRecorded /> },
    { term: INVENTORY_FIELDS.packSize, value: inventory.pack_size ?? <NotRecorded /> },
    {
      term: INVENTORY_FIELDS.gtin,
      value: inventory.gtin ? (
        <span className="mono">
          <Highlighted text={inventory.gtin} parts={inventoryParts} />
        </span>
      ) : (
        <NotRecorded />
      ),
    },
    {
      term: INVENTORY_FIELDS.lot,
      value: inventory.lot_code ? (
        <span className="mono">
          <Highlighted text={inventory.lot_code} parts={inventoryParts} />
        </span>
      ) : (
        <NotRecorded />
      ),
    },
    {
      term: INVENTORY_FIELDS.brand,
      value: inventory.brand ? (
        <Highlighted text={inventory.brand} parts={inventoryParts} />
      ) : (
        <NotRecorded />
      ),
    },
    {
      term: INVENTORY_FIELDS.manufacturer,
      value: inventory.manufacturer ? (
        <Highlighted text={inventory.manufacturer} parts={inventoryParts} />
      ) : (
        <NotRecorded />
      ),
    },
    {
      term: INVENTORY_FIELDS.mfrItem,
      value: inventory.manufacturer_item_code ? (
        <span className="mono">
          <Highlighted text={inventory.manufacturer_item_code} parts={inventoryParts} />
        </span>
      ) : (
        <NotRecorded />
      ),
    },
    { term: INVENTORY_FIELDS.vendor, value: inventory.vendor_name ?? <NotRecorded /> },
    {
      term: INVENTORY_FIELDS.vendorItem,
      value: inventory.vendor_item_code ? (
        <span className="mono">{inventory.vendor_item_code}</span>
      ) : (
        <NotRecorded />
      ),
      hint: VENDOR_ITEM_HINT,
    },
    { term: INVENTORY_FIELDS.unitCost, value: unitCost ?? <NotRecorded /> },
  ];

  const recallItems: DefinitionItem[] = [
    {
      term: RECALL_FIELDS.record,
      value: <span className="mono">{recall.source_record_id}</span>,
      hint: (
        <>
          {recall.source}{" "}
          <ProvenanceLabel
            provenance={recall.provenance}
            label={recall.provenance_label}
          />
        </>
      ),
    },
    {
      term: RECALL_FIELDS.firm,
      value: recall.recalling_firm ? (
        <Highlighted text={recall.recalling_firm} parts={recallParts} />
      ) : (
        <NotRecorded />
      ),
    },
    { term: RECALL_FIELDS.classification, value: recall.classification ?? UNCLASSIFIED },
    {
      term: RECALL_FIELDS.status,
      value: recall.status,
      hint: recall.prior_status
        ? `was ${recall.prior_status}${
            recall.status_changed_at
              ? `, changed ${formatDateTime(recall.status_changed_at, timeZone)}`
              : ""
          }${recall.amended_from ? `. Amends record #${recall.amended_from}` : ""}`
        : recall.amended_from
          ? `Amends record #${recall.amended_from}`
          : undefined,
    },
    {
      term: RECALL_FIELDS.reported,
      value: formatDate(recall.report_date, timeZone) ?? <NotRecorded />,
    },
    {
      term: RECALL_FIELDS.received,
      value: formatDateTime(recall.received_at, timeZone) ?? recall.received_at,
      hint: RECEIVED_AT_HINT,
    },
    { term: RECALL_FIELDS.reason, value: recall.reason_for_recall ?? <NotRecorded /> },
    {
      term: RECALL_FIELDS.codeInfo,
      value: recall.code_info ? (
        <span className={styles.codeInfo}>
          <Highlighted text={recall.code_info} parts={recallParts} />
        </span>
      ) : (
        <span className={styles.absent}>{NO_CODE_INFO}</span>
      ),
    },
  ];

  const matchRow: DefinitionItem[] = [
    { term: MATCH_ROW_FIELDS.id, value: <span className="mono">{match.id}</span> },
    {
      term: MATCH_ROW_FIELDS.run,
      value: <span className="mono">#{run.id}</span>,
      hint: `${run.channel.replace(/_/g, " ")}, inventory of ${run.business_date}`,
    },
    {
      term: MATCH_ROW_FIELDS.created,
      value: formatDateTime(match.created_at, timeZone) ?? match.created_at,
    },
    {
      term: MATCH_ROW_FIELDS.isNew,
      value: match.is_new ? "yes" : "no",
      hint: IS_NEW_HINT,
    },
    {
      term: MATCH_ROW_FIELDS.evidence,
      value: <span className="mono">{match.evidence_kind}</span>,
    },
    {
      term: MATCH_ROW_FIELDS.inventoryId,
      value: <span className="mono">#{inventory.id}</span>,
    },
    { term: MATCH_ROW_FIELDS.recallId, value: <span className="mono">#{recall.id}</span> },
    {
      term: MATCH_ROW_FIELDS.score,
      value:
        match.score === null ? (
          <NotRecorded word={NO_SCORE} />
        ) : (
          <span className="mono">{match.score}</span>
        ),
      hint: SCORE_HINT,
    },
  ];

  return (
    <>
      <p className={styles.crumb}>
        <Link href={header.is_current ? "/sheet" : "/runs"}>
          <span aria-hidden="true">&larr;</span>{" "}
          {header.is_current ? backToSheet(run.id) : BACK_TO_RUNS}
        </Link>
      </p>

      <PageHeader
        title={MATCH_TITLE}
        context={matchContext(match.id, run.id, inventory.storage_location)}
        actions={<PrintButton label={PRINT_LABEL["/match"]} />}
      />

      <Verdict
        match={match}
        recall={recall}
        clearedBy={clearedBy}
        clearedCount={clearings.length}
        timeZone={timeZone}
      />

      <p className={styles.bothRecords}>{BOTH_RECORDS_NOTE}</p>

      <div className={styles.sides}>
        <RecordSide
          title={INVENTORY_HEADING}
          verbatimLabel={INVENTORY_VERBATIM_LABEL}
          verbatimText={inventory.raw_description}
          parts={inventoryParts}
          items={inventoryItems}
          trigger={match.trigger_inventory_text}
          missing={inventoryParts.filter((part) => !inventoryFound.has(part))}
          extras={
            inventory.unpopulated_fields.length > 0 || inventory.merged_from ? (
              <>
                {inventory.unpopulated_fields.length > 0 ? (
                  <p>{unpopulatedFields(inventory.unpopulated_fields)}</p>
                ) : null}
                {inventory.merged_from ? <p>{mergedFrom(inventory.merged_from)}</p> : null}
              </>
            ) : null
          }
        />

        <RecordSide
          title={RECALL_HEADING}
          note={
            <ProvenanceLabel
              provenance={recall.provenance}
              label={recall.provenance_label}
            />
          }
          verbatimLabel={RECALL_VERBATIM_LABEL}
          verbatimText={recall.product_description}
          parts={recallParts}
          items={recallItems}
          trigger={match.trigger_recall_text}
          missing={recallParts.filter((part) => !recallFound.has(part))}
        />
      </div>

      <div className={styles.decisions}>
        <LineDecisions detail={detail} timeZone={timeZone} />
      </div>

      <div className={styles.appendix}>
        <Panel title={MATCH_ROW_HEADING} printBlock>
          <DefinitionList items={matchRow} columns={2} />
        </Panel>

        <AgencyRecord raw={recall.raw_json} />
      </div>
    </>
  );
}
