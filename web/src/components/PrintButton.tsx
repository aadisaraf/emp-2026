"use client";

import { cx } from "@/lib/cx";
import styles from "./PrintButton.module.css";

export interface PrintButtonProps {
  /** Two or three words. It is a button, not a sentence. */
  label?: string;
  /** primary is the green button; plain is the bordered one. */
  variant?: "primary" | "plain";
}

/**
 * Print. The printed sheet is the legal artefact, so this is not an
 * afterthought action tucked into a menu.
 */
export function PrintButton({ label = "Print sheet", variant = "plain" }: PrintButtonProps) {
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
