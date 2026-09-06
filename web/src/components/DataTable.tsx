import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "@/lib/cx";
import styles from "./DataTable.module.css";

/** How a column is read, which decides its alignment and its face. */
export type ColumnVariant = "text" | "measure" | "identifier";

export interface Column<T> {
  /** Stable key, also used as the sort key. */
  key: string;
  header: ReactNode;
  render: (row: T, index: number) => ReactNode;
  variant?: ColumnVariant;
  /** A fixed width, e.g. "84px". Leave off for the columns that take the rest. */
  width?: string;
  /** A 1px rule on this column's left edge, to separate a group of columns. */
  groupEdge?: boolean;
  /** Draw the sort affordance on this header. */
  sortable?: boolean;
  headerTitle?: string;
}

export interface DataTableSort {
  key: string;
  direction: "asc" | "desc";
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: readonly T[];
  rowKey: (row: T, index: number) => string | number;
  /** Read by screen readers. Hidden visually unless showCaption is set. */
  caption?: ReactNode;
  showCaption?: boolean;
  /** Stick the header under the masthead while the body scrolls. */
  sticky?: boolean;
  /**
    Which column the rows arrived sorted by. Presentational only: this
    component never reorders anything. The pull sheet arrives in one total
  */
  sort?: DataTableSort;
  rowClassName?: (row: T, index: number) => string | undefined;
  rowAttributes?: (row: T, index: number) => HTMLAttributes<HTMLTableRowElement>;
  /** What a table with no rows says. A zero-row result is still a result. */
  empty?: ReactNode;
  /**
   * Wrap the table in a horizontal scroller. Leave this off when sticky is on:
   * a scroll container is what the sticky header sticks to.
   */
  scroll?: boolean;
  className?: string;
}

/**
  The table. Dense, bordered, hairline row rules, no zebra striping, no card
  per row, and no shadow except the one hairline under a stuck header.
*/
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  showCaption,
  sticky,
  sort,
  rowClassName,
  rowAttributes,
  empty,
  scroll,
  className,
}: DataTableProps<T>) {
  const table = (
    <table className={cx(styles.table, sticky && styles.sticky, className)}>
      {caption ? (
        <caption className={showCaption ? styles.caption : "sr-only"}>{caption}</caption>
      ) : null}
      <colgroup>
        {columns.map((column) => (
          <col key={column.key} style={column.width ? { width: column.width } : undefined} />
        ))}
      </colgroup>
      <thead>
        <tr>
          {columns.map((column) => {
            const sorted = sort?.key === column.key;
            return (
              <th
                key={column.key}
                scope="col"
                title={column.headerTitle}
                aria-sort={
                  sorted ? (sort.direction === "asc" ? "ascending" : "descending") : undefined
                }
                className={cx(
                  styles.head,
                  column.variant === "measure" && styles.measure,
                  column.variant === "identifier" && styles.identifier,
                  column.groupEdge && styles.groupEdge,
                  column.sortable && styles.sortable,
                )}
              >
                <span className={styles.headText}>
                  {column.header}
                  {sorted ? (
                    <span aria-hidden="true" className={styles.sortMark}>
                      {sort.direction === "asc" ? "▲" : "▼"}
                    </span>
                  ) : null}
                </span>
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && empty ? (
          <tr>
            <td className={styles.emptyCell} colSpan={columns.length}>
              {empty}
            </td>
          </tr>
        ) : null}
        {rows.map((row, index) => (
          <tr
            key={rowKey(row, index)}
            className={cx(styles.row, rowClassName?.(row, index))}
            {...rowAttributes?.(row, index)}
          >
            {columns.map((column) => (
              <td
                key={column.key}
                className={cx(
                  styles.cell,
                  column.variant === "measure" && styles.measure,
                  column.variant === "identifier" && styles.identifier,
                  column.groupEdge && styles.groupEdge,
                )}
              >
                {column.render(row, index)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );

  return scroll ? <div className={styles.scroll}>{table}</div> : table;
}
