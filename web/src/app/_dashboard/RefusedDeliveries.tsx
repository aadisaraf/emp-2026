import type { Run } from "@/lib/api";
import { NotRecorded, Panel, StatusBadge } from "@/components";
import { formatDateTime, shortDeliveryRef } from "@/lib/format";
import { channelLabel } from "@/lib/strings";
import { PANEL, REFUSED_NOTE } from "./strings";
import styles from "./dashboard.module.css";

export interface RefusedDeliveriesProps {
  /** The 5 most recent refused deliveries, newest first. Never rendered empty. */
  runs: Run[];
}

/**
 * Deliveries that were refused.
 *
 * A rejection is louder than a quiet morning, so it gets a 2px outline and the
 * word REJECTED, and the reason is printed in full rather than clipped into a
 * table cell. A refused delivery never overwrote the sheet: the run above is
 * still the last export that was read, unchanged.
 *
 * This section does not render at all when nothing was refused. An empty panel
 * saying every delivery succeeded is noise on every normal day, and noise on a
 * normal day is how the abnormal day gets missed.
 */
export function RefusedDeliveries({ runs }: RefusedDeliveriesProps) {
  return (
    <Panel title={PANEL.refused} note={REFUSED_NOTE} printBlock>
      <div className={styles.refusedList}>
        {runs.map((run) => (
          <div className={styles.refused} key={run.id}>
            <div className={styles.refusedHead}>
              <StatusBadge value="rejected" />
              <span className={styles.refusedRef}>
                {shortDeliveryRef(run.delivery_ref) ?? <NotRecorded />}
              </span>
              <span className={styles.refusedMeta}>
                run #{run.id} · {run.business_date} · {channelLabel(run.channel)} ·{" "}
                {formatDateTime(run.started_at) ?? run.started_at}
              </span>
            </div>
            <p className={styles.refusedReason}>
              {run.rejection_reason ?? <NotRecorded />}
            </p>
          </div>
        ))}
      </div>
    </Panel>
  );
}
