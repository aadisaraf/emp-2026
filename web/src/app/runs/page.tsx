import Link from "next/link";
import {
  Chip,
  ChipRow,
  EmptyState,
  ErrorState,
  Facts,
  Note,
  PageHero,
  Pill,
  TabCard,
  Tag,
  ui,
} from "@/components";
import { attempt, getRuns } from "@/lib/api";
import { EMPTY_NO_DELIVERIES, EMPTY_NO_RUNS, PAGE_TITLES } from "@/lib/strings";
import { formatCount, formatDate, formatTime } from "@/lib/format";
import { cx } from "@/lib/cx";
import type { RunHistoryEntry } from "@/lib/types";
import { RunDayStrip } from "./_components/RunDayStrip";
import { NO_FILE_READ, channelLabel, showingNote } from "./_components/runsMeta";

/* Run history: every delivery, refused ones included. */

export const dynamic = "force-dynamic";

/** The API caps this at 200. Ask for all of them: a run history that pages is
 *  a run history with a week of failures on page two. */
const LIMIT = 200;

function StatusChip({ status }: { status: RunHistoryEntry["status"] }) {
  if (status === "rejected") return <Chip tone="pull">refused</Chip>;
  if (status === "running") return <Chip tone="held">running</Chip>;
  return <Chip tone="done">read</Chip>;
}

function RunRow({ run, current }: { run: RunHistoryEntry; current: boolean }) {
  const refused = run.status === "rejected";
  return (
    <tr>
      <td>
        <Link href={`/runs/${run.id}`} className={ui.open}>
          <span className={ui.lead}>{formatDate(run.business_date) ?? run.business_date}</span>
          <span className={ui.sub}>
            {formatTime(run.finalized_at ?? run.started_at) ?? "—"}
          </span>
        </Link>
      </td>
      <td>
        <ChipRow>
          <span>#{run.id}</span>
          {current ? <Chip tone="done">current</Chip> : null}
        </ChipRow>
      </td>
      <td>
        <span className={ui.lead}>{channelLabel(run.channel)}</span>
        {refused && run.rejection_reason ? (
          <span className={ui.sub}>{run.rejection_reason}</span>
        ) : null}
      </td>
      <td className={cx(ui.num, ui.opt)}>
        {run.channel === "rematch" ? NO_FILE_READ : (formatCount(run.rows_read) ?? "0")}
      </td>
      <td className={ui.num}>{refused ? "—" : (formatCount(run.pull_count) ?? "0")}</td>
      <td className={cx(ui.num, ui.optSm)}>{refused ? "—" : (formatCount(run.held_count) ?? "0")}</td>
      <td className={cx(ui.num, ui.optSm)}>{refused ? "—" : (formatCount(run.new_count) ?? "0")}</td>
      <td>
        <StatusChip status={run.status} />
      </td>
    </tr>
  );
}

export default async function RunHistoryPage() {
  const result = await attempt(getRuns(LIMIT));

  if (!result.ok) {
    return (
      <>
        <PageHero figure="—" word={PAGE_TITLES.runHistory} />
        <ErrorState failure={result.error} />
      </>
    );
  }

  const { runs, run_count: runCount, current_run_id: currentRunId, generated_at } = result.data;

  if (runs.length === 0) {
    return (
      <>
        <PageHero figure="0" word={PAGE_TITLES.runHistory} />
        <EmptyState
          heading={EMPTY_NO_DELIVERIES}
          body={EMPTY_NO_RUNS.body}
          action={EMPTY_NO_RUNS.action}
        />
      </>
    );
  }

  const refused = runs.filter((run) => run.status === "rejected").length;
  const truncated = runs.length < runCount;
  const newest = runs[0];

  return (
    <>
      <PageHero
        figure={formatCount(runCount) ?? "0"}
        word={runCount === 1 ? "delivery read" : "deliveries read"}
        actions={
          <>
            {refused > 0 ? <Tag tone="alert">{formatCount(refused)} refused</Tag> : null}
            <Pill href="/ingest" tone="primary">
              Add inventory
            </Pill>
          </>
        }
      />

      <Facts
        items={[
          { label: "latest", value: `#${newest.id}` },
          {
            label: "received",
            value: formatDate(newest.business_date) ?? newest.business_date,
          },
          { label: "channel", value: channelLabel(newest.channel) },
          {
            label: "refused",
            value: formatCount(refused) ?? "0",
            tone: refused > 0 ? "alert" : "plain",
          },
        ]}
      />

      <RunDayStrip runs={runs} generatedAt={generated_at} />

      <TabCard title="Every delivery" count={formatCount(runs.length)} flush>
        <table className={ui.rec}>
          <caption>
            Every delivery this location has made, newest first, including the ones that were
            refused.
          </caption>
          <colgroup>
            <col style={{ width: "140px" }} />
            <col style={{ width: "110px" }} />
            <col />
            <col className={ui.opt} style={{ width: "90px" }} />
            <col style={{ width: "80px" }} />
            <col className={ui.optSm} style={{ width: "80px" }} />
            <col className={ui.optSm} style={{ width: "70px" }} />
            <col style={{ width: "100px" }} />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">Received</th>
              <th scope="col">Run</th>
              <th scope="col">Channel</th>
              <th scope="col" className={cx(ui.num, ui.opt)}>
                Rows
              </th>
              <th scope="col" className={ui.num}>
                Pull
              </th>
              <th scope="col" className={cx(ui.num, ui.optSm)}>
                Held
              </th>
              <th scope="col" className={cx(ui.num, ui.optSm)}>
                New
              </th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <RunRow key={run.id} run={run} current={run.id === currentRunId} />
            ))}
          </tbody>
        </table>
      </TabCard>

      {truncated ? <Note>{showingNote(runs.length, runCount)}</Note> : null}
    </>
  );
}
