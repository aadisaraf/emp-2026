import styles from "./NotRecorded.module.css";
import { NOT_RECORDED } from "@/lib/strings";

export interface NotRecordedProps {
  /** Override only for a field where a different word is the true one. */
  word?: string;
}

/**
 * What an empty field says. 50 of the 56 export rows carry no barcode and 11
 * carry no lot code; a blank cell there would read as zero, and "N/A" reads as
 * "not applicable", which is a different claim from "the export did not carry
 * this".
 */
export function NotRecorded({ word = NOT_RECORDED }: NotRecordedProps) {
  return <span className={styles.missing}>{word}</span>;
}
