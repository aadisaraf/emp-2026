import { DefinitionList, PageHeader, Panel } from "@/components";
import { API_BASE } from "@/lib/api";
import { PAGE_TITLES } from "@/lib/strings";
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

export default function AddInventoryPage() {
  return (
    <>
      <PageHeader
        title={PAGE_TITLES.addInventory}
        context="The scheduled drop is the normal path. This page is for the morning it fails."
      />

      <Panel title="Upload one export">
        <p className={styles.lede}>
          The file is read once, matched against the recall corpus, and finalized as a
          run of its own. It does not replace the scheduled drop.
        </p>
        <a className={styles.action} href={`${API_BASE}/ingest`}>
          Open the upload form
        </a>
        <p className={styles.note}>
          Accepts CSV and XLSX. A file that cannot be read is refused by name, with the
          row or column that failed, and the sheet on screen is left alone.
        </p>
      </Panel>

      <Panel title="Where inventory comes from">
        <DefinitionList
          items={CHANNELS.map((channel) => ({
            term: channel.term,
            value: (
              <>
                {channel.detail}
                {channel.path ? <code className={styles.path}>{channel.path}</code> : null}
              </>
            ),
          }))}
        />
      </Panel>
    </>
  );
}
