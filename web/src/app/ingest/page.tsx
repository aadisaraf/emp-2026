import { Facts, Kv, PageHero, Pill, TabCard } from "@/components";
import { attempt, getStatus } from "@/lib/api";
import { channelLabel } from "@/lib/strings";
import { formatCount, formatDate } from "@/lib/format";
import { UploadPanel } from "./UploadPanel";
import styles from "./ingest.module.css";

/*
  The three ways an export reaches this location, and what to do when the
  scheduled one does not arrive.
*/

export const dynamic = "force-dynamic";

const CHANNELS = [
  {
    term: "SFTP drop",
    detail:
      "The normal path. Your inventory software writes one export a morning into " +
      "the drop directory and PullSheet reads it. Nobody signs in. Files are read " +
      "only once they have finished writing, and a file that is read successfully " +
      "moves to the archive.",
    path: "data/watched/",
  },
  {
    /*
      Deliberately not described as working mail. The reader is real and
      tested, and an attachment parses into exactly the same record as a
      dropped file. What does not exist is a mail server: nothing here
    */
    term: "Email",
    detail:
      "The same reader, behind an attachment instead of a file. There is no " +
      "mail server: this reads a committed fixture mailbox, so it demonstrates " +
      "that a row parses identically either way and nothing more.",
    path: "data/fixtures/inbox.mbox",
  },
  {
    term: "Upload",
    detail:
      "For the morning the scheduled drop does not arrive. One file, read once. " +
      "If a column heading is ambiguous you are asked about that heading, and the " +
      "answer is remembered.",
    path: null,
  },
];

export default async function AddInventoryPage() {
  const result = await attempt(getStatus());
  const status = result.ok ? result.data : null;
  const run = status?.run ?? null;

  return (
    <>
      {/* The figure is the run a new file would replace, because that is the
          thing a person is deciding about when they stand on this page. */}
      <PageHero
        figure={run ? `#${run.id}` : "0"}
        word={run ? "in force now" : "deliveries so far"}
        actions={run ? <Pill href="/sheet">Open sheet</Pill> : undefined}
      />

      {run ? (
        <Facts
          items={[
            { label: "channel", value: channelLabel(run.channel) },
            {
              label: "received",
              value: formatDate(run.business_date) ?? run.business_date,
            },
            { label: "rows read", value: formatCount(run.rows_read) ?? "0" },
            { label: "deliveries", value: formatCount(status?.run_count ?? 0) ?? "0" },
          ]}
        />
      ) : null}

      <UploadPanel />

      <TabCard title="Where inventory comes from" tone="sunken">
        {CHANNELS.map((channel) => (
          <Kv
            key={channel.term}
            term={channel.term}
            value={
              <>
                {channel.detail}
                {channel.path ? <code className={styles.path}>{channel.path}</code> : null}
              </>
            }
          />
        ))}
      </TabCard>
    </>
  );
}
