import Link from "next/link";
import { Icon } from "@/components/Icon";
import { cx } from "@/lib/cx";
import styles from "./dashboard.module.css";

/* The way in, at the foot of the screen, on every morning. */
export function FloatingBar({ hasRun }: { hasRun: boolean }) {
  return (
    <div className={cx(styles.floating, "no-print")}>
      <span className={styles.floatingText}>
        <Icon name="add" size={16} />
        {hasRun ? "Drop tomorrow's export" : "Drop today's export to start"}
      </span>
      <Link href="/ingest" className={styles.floatingButton}>
        + Add inventory
      </Link>
    </div>
  );
}
