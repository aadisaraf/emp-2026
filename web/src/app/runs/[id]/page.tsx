import Link from "next/link";
import {
  ClockStrip,
  DefinitionList,
  ErrorState,
  NotRecorded,
  PageHeader,
  Panel,
  StatRail,
  StatusBadge,
  type DefinitionItem,
  type StatRailItem,
} from "@/components";
import { attempt, getRun, isNotFound } from "@/lib/api";
import { CLOCKS } from "@/lib/strings";
import { formatCount, formatDateTime, shortDeliveryRef } from "@/lib/format";
import { CorpusInForce } from "../_components/CorpusInForce";
import { NewLinesTable } from "../_components/NewLinesTable";
import { Tag } from "../_components/Tag";
import {
  BACK_LINK,
  CLOCKS_PANEL_NOTE,
  NEW_PANEL_NOTE,
  NO_FILE_ARRIVED,
  NO_FILE_READ,
  PRODUCED_NOTE,
  REJECTED_BODY,
  REJECTED_HEADING,
  REMATCH_ROWS_TITLE,
  RUN_FOOTER,
  RUN_NOT_FOUND_DETAIL,
  RUN_NOT_FOUND_HEADING,
  SHEET_LINK,
  channelExplanation,
  channelLabel,
  decidedBeforeNote,
  hasDelivery,
  newAgainst,
} from "../_components/runsMeta";
import styles from "./page.module.css";

/* One run. */

export const dynamic = "force-dynamic";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const runId = Number.parseInt(id, 10);

  if (!Number.isInteger(runId) || runId < 1) {
    return (
      <>
        <Back />
        <PageHeader title="Run" />
        <ErrorState
          heading={RUN_NOT_FOUND_HEADING}
          detail={RUN_NOT_FOUND_DETAIL}
          failure={{
            kind: "http",
            status: 404,
            code: "no_run",
            message: `"${id}" is not a run id.`,
            url: "",
          }}
        />
      </>
    );
  }

  const result = await attempt(getRun(runId));

  if (!result.ok) {
    return (
      <>
        <Back />
        <PageHeader title={`Run #${runId}`} />
        <ErrorState
          failure={result.error}
          heading={isNotFound(result.error) ? RUN_NOT_FOUND_HEADING : undefined}
          detail={isNotFound(result.error) ? RUN_NOT_FOUND_DETAIL : undefined}
        />
      </>
    );
  }

  const { run, header, previous_run_id, decided_before, new_lines, deadlines } =
    result.data;
  const accepted = run.status === "ok";
  const delivered = hasDelivery(run);

  const arrived: DefinitionItem[] = [
    {
      term: "Channel",
      value: channelLabel(run.channel),
      hint: channelExplanation(run.channel),
    },
    {
      term: "Delivery",
      value: delivered ? (
        (shortDeliveryRef(run.delivery_ref) ?? <NotRecorded />)
      ) : (
        <span className={styles.noFile}>{NO_FILE_ARRIVED}</span>
      ),
      hint: delivered && run.delivery_ref ? run.delivery_ref : undefined,
    },
    { term: "Started", value: formatDateTime(run.started_at) ?? run.started_at },
    {
      term: "Finalized",
      value:
        formatDateTime(run.finalized_at) ??
        (run.status === "running" ? "this run has not finished" : <NotRecorded />),
    },
    {
      term: "Rows read",
      value: delivered ? (
        formatCount(run.rows_read)
      ) : (
        <span className={styles.noFile} title={REMATCH_ROWS_TITLE}>
          {NO_FILE_READ}
        </span>
      ),
      hint: delivered ? undefined : REMATCH_ROWS_TITLE,
    },
    {
      term: "Rows kept with an unreadable field",
      value: formatCount(run.rows_partial),
      hint:
        run.rows_partial > 0
          ? "Kept, not dropped. A row with one field this build could not read is still inventory."
          : undefined,
    },
  ];

  if (run.column_map) {
    const mapped = Object.entries(run.column_map);
    arrived.push({
      term: "Column map",
      value: (
        <span className={styles.columnMap}>
          {mapped.map(([from, to]) => `${from} to ${to}`).join(" · ")}
        </span>
      ),
      hint: "How this delivery's headings were read into the fields the matcher uses.",
    });
  }

  const produced: StatRailItem[] = [
    { label: "Pull", value: formatCount(header.counts.pull_count) },
    { label: "Held", value: formatCount(header.counts.held_count) },
    {
      label: "New",
      value: formatCount(header.counts.new_count),
      title: "Lines that were not on the previous accepted run.",
    },
    { label: "Lines", value: formatCount(header.counts.total) },
  ];

  return (
    <>
      <Back />

      <PageHeader
        title={`Run #${run.id}`}
        context={
          <>
            Inventory of {run.business_date} · {channelLabel(run.channel)}
            {header.is_current ? (
              <>
                {" "}
                <Tag title="The most recent accepted run. This is the sheet in force.">
                  current
                </Tag>
              </>
            ) : null}
          </>
        }
        actions={<StatusBadge value={run.status} />}
      />

      <div className={styles.stack}>
        {accepted ? null : (
          <Panel title={REJECTED_HEADING} printBlock>
            {run.rejection_reason ? (
              <p className={styles.reason}>{run.rejection_reason}</p>
            ) : (
              <p className={styles.reason}>
                {run.status === "running"
                  ? "This run started and has not finalized, so it has no frozen counts yet."
                  : "No reason was recorded against this run."}
              </p>
            )}
            <p className={styles.body}>{REJECTED_BODY}</p>
          </Panel>
        )}

        <Panel title="What arrived" printBlock>
          <DefinitionList items={arrived} columns={2} />
        </Panel>

        {accepted ? (
          <Panel title="What it produced" note={PRODUCED_NOTE} printBlock>
            <StatRail items={produced} className={styles.rail} />
            <p className={styles.body}>{newAgainst(header.counts.new_count, previous_run_id)}</p>
            <p className={styles.links}>
              <Link href={`/sheet/${run.id}`}>{SHEET_LINK}</Link>
              <span className={styles.linkRule} aria-hidden="true" />
              <Link href={`/artifacts/hold?run=${run.id}`}>Hold record</Link>
              <span className={styles.linkRule} aria-hidden="true" />
              <Link href={`/artifacts/credit-claim?run=${run.id}`}>Credit claim</Link>
              {header.location.serves_meal_program ? (
                <>
                  <span className={styles.linkRule} aria-hidden="true" />
                  <Link href={`/artifacts/state-report?run=${run.id}`}>State report</Link>
                </>
              ) : null}
            </p>
          </Panel>
        ) : null}

        <CorpusInForce header={header} />

        <Panel title={CLOCKS.heading} note={CLOCKS_PANEL_NOTE} printBlock>
          <ClockStrip deadlines={deadlines} variant="table" notes />
        </Panel>

        {new_lines.length > 0 ? (
          <Panel title="New on this run" note={NEW_PANEL_NOTE} flush printBlock>
            <NewLinesTable lines={new_lines} />
          </Panel>
        ) : null}

        <footer className={styles.footer}>
          <p className={styles.note}>{RUN_FOOTER}</p>
          {decided_before ? (
            <p className={styles.note}>
              {decidedBeforeNote(formatDateTime(decided_before) ?? decided_before)}
            </p>
          ) : null}
        </footer>
      </div>
    </>
  );
}

function Back() {
  return (
    <p className={styles.crumb}>
      <Link href="/runs">
        <span aria-hidden="true">←</span> {BACK_LINK}
      </Link>
    </p>
  );
}
