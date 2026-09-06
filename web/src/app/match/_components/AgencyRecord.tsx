import { AGENCY_RECORD_HEADING, AGENCY_RECORD_NOTE } from "./strings";
import styles from "./AgencyRecord.module.css";

export interface AgencyRecordProps {
  raw: Record<string, unknown>;
}

/**
 * The agency payload the recall record was built from.
 *
 * It is here because this page is the one that gets opened when somebody asks
 * how the system knows, and the answer eventually bottoms out in the bytes the
 * agency published. Every field above is parsed out of this; nothing here is
 * read to decide anything, and the keys differ between openFDA and FSIS, so it
 * is shown as text rather than as a table pretending the shape is fixed.
 *
 * It is closed by default because it is the floor under the floor and it is
 * long. Every fact a decision rests on is rendered above it, in place.
 */
export function AgencyRecord({ raw }: AgencyRecordProps) {
  const keys = Object.keys(raw);
  if (keys.length === 0) return null;

  return (
    <details className={styles.wrap}>
      <summary className={styles.summary}>
        {AGENCY_RECORD_HEADING}
        <span className={styles.count}>
          {keys.length} {keys.length === 1 ? "field" : "fields"}
        </span>
      </summary>
      <p className={styles.note}>{AGENCY_RECORD_NOTE}</p>
      <pre className={styles.json}>{JSON.stringify(raw, null, 2)}</pre>
    </details>
  );
}
