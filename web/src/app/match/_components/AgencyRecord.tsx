import { AGENCY_RECORD_HEADING, AGENCY_RECORD_NOTE } from "./strings";
import styles from "./AgencyRecord.module.css";

/** The agency payload the recall record was built from. */
export function AgencyRecord({ raw }: {
  raw: Record<string, unknown>;
}) {
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
