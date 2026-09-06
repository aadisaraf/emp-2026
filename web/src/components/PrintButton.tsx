"use client";

import { cx } from "@/lib/cx";
import styles from "./PrintButton.module.css";

/** Print. The printed sheet is the legal artefact, so it gets a real button. */
export function PrintButton({ label = "Print sheet", variant = "plain" }: {
  /** Two or three words. It is a button, not a sentence. */
  label?: string;
  /** primary is the green button; plain is the bordered one. */
  variant?: "primary" | "plain";
}) {
  return (
    <button
      type="button"
      className={cx(styles.button, variant === "primary" && styles.primary, "no-print")}
      onClick={() => window.print()}
    >
      {label}
    </button>
  );
}
