import type { ReactNode } from "react";
import styles from "./SignatureBlock.module.css";

interface SignatureBlockProps {
  heading: string;
  /** Why these are blank. One or two sentences, no more. */
  note?: ReactNode;
  /** The field labels, from the payload. Values are never passed, ever. */
  fields: string[];
}

/** Ruled lines for a pen. */
export function SignatureBlock({ heading, note, fields }: SignatureBlockProps) {
  return (
    <section className={styles.block}>
      <h2 className={styles.heading}>{heading}</h2>
      {note ? <p className={styles.note}>{note}</p> : null}
      <div className={styles.fields}>
        {fields.map((field) => (
          <div className={styles.field} key={field}>
            <span className={styles.label}>{field}</span>
            <span className={styles.rule} aria-hidden="true" />
          </div>
        ))}
      </div>
    </section>
  );
}
