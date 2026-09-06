import { DataTable } from "@/components";
import type { SheetLine, SheetSection } from "@/lib/api";
import { sectionTally } from "@/lib/strings";
import { sheetColumns } from "./sheetColumns";
import type { ClearedFacts } from "./clearedFacts";
import styles from "./sheet.module.css";

export interface StorageSectionsProps {
  sections: SheetSection[];
  cleared: ClearedFacts;
}

/*
  One table per storage location, in the order the API sent them, which is the
  cooler with the recalled chicken before the dry store with a maybe.
*/

export function StorageSections({ sections, cleared }: StorageSectionsProps) {
  const columns = sheetColumns(cleared);

  return (
    <>
      {sections.map((section) => (
        <section className={styles.section} key={section.storage_location}>
          <h2 className={styles.sectionHead}>
            <span className={styles.sectionName}>{section.storage_location}</span>
            <span className={styles.sectionTally}>
              {sectionTally(section.pull, section.held, section.cleared)}
            </span>
          </h2>
          <DataTable<SheetLine>
            className={styles.sheetTable}
            columns={columns}
            rows={section.lines}
            rowKey={(line) => line.id}
            /*
              Today's "new since the previous run" list links to /sheet#match-N.
              Without this the fragment lands nowhere and the browser stays at
              the top of an 856 line sheet.
            */
            rowAttributes={(line) => ({ id: `match-${line.id}` })}
            caption={`${section.storage_location}: ${sectionTally(
              section.pull,
              section.held,
              section.cleared,
            )}`}
            sticky
          />
        </section>
      ))}
    </>
  );
}
