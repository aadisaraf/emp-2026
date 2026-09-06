import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "@/lib/cx";
import styles from "./DataTable.module.css";

/** How a column is read, which decides its alignment and its face. */
export type ColumnVariant = "text" | "measure" | "identifier";

export interface Column<T> {
  /** Stable key, unique within the table. */
  key: string;
  header: ReactNode;
  render: (row: T, index: number) => ReactNode;
  variant?: ColumnVariant;
  /** A fixed width, e.g. "84px". Leave off for the columns that take the rest. */
  width?: string;
  /** A 1px rule on this column's left edge, to separate a group of columns. */
  groupEdge?: boolean;
  headerTitle?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: readonly T[];
  rowKey: (row: T, index: number) => string | number;
  /** Read by screen readers. Never shown. */
  caption: ReactNode;
  /** Stick the header under the masthead while the body scrolls. */
  sticky?: boolean;
  rowClassName?: (row: T, index: number) => string | undefined;
  rowAttributes?: (row: T, index: number) => HTMLAttributes<HTMLTableRowElement>;
  /** What a table with no rows says. A zero-row result is still a result. */
  empty?: ReactNode;
  /** Wrap in a horizontal scroller. Leave off when sticky is on. */
  scroll?: boolean;
  className?: string;
}

/* Dense, hairline rules, no zebra striping. */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  sticky,
  rowClassName,
  rowAttributes,
  empty,
  scroll,
  className,
}: DataTableProps<T>) {
  const table = (
    <table className={cx(styles.table, sticky && styles.sticky, className)}>
      <caption className="sr-only">{caption}</caption>
      <colgroup>
        {columns.map((column) => (
          <col key={column.key} style={column.width ? { width: column.width } : undefined} />
        ))}
      </colgroup>
      <thead>
        <tr>
          {columns.map((column) => (
            <th
              key={column.key}
              scope="col"
              title={column.headerTitle}
              className={cx(
                styles.head,
                column.variant === "measure" && styles.measure,
                column.variant === "identifier" && styles.identifier,
                column.groupEdge && styles.groupEdge,
              )}
            >
              {column.header}
            </th>
          ))}
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
