import Link from "next/link";
import type { MenuEntry, MenuProposal, MenuSummary } from "@/lib/api";
import {
  ClearedMark,
  DataTable,
  NotRecorded,
  Panel,
  ProvenanceLabel,
  StatRail,
  StatusBadge,
  TierBadge,
  type Column,
  type StatRailItem,
} from "@/components";
import { formatCount, formatQuantity } from "@/lib/format";
import { UNCLASSIFIED } from "@/lib/strings";
import { PlannedMeals } from "./PlannedMeals";
import { brokenMeals, proposalCounts, scheduledMealCount, type BrokenMeal } from "./join";
import { MENU, cascadeCounts, heldNotCascaded, plannedTitle } from "./copy";
import styles from "./impact.module.css";

export interface MenuPanelProps {
  menu: MenuSummary;
  proposals: MenuProposal[];
  runId: number;
  servesMealProgram: boolean;
}

/** The cascade: which planned meals a pull takes off the menu. */
export function MenuPanel({ menu, proposals, runId, servesMealProgram }: MenuPanelProps) {
  const rows = brokenMeals(menu, proposals);
  const counts = proposalCounts(proposals);

  const items: StatRailItem[] = [
    {
      label: MENU.rail.plannedMeals,
      value: <PlannedMeals count={menu.planned_meals} caveat={menu.caveat} tag={false} />,
      title: plannedTitle(menu.caveat),
    },
    { label: MENU.rail.serviceDays, value: formatCount(menu.dates.length) },
    { label: MENU.rail.itemsBroken, value: formatCount(proposals.length) },
    { label: MENU.rail.substituted, value: formatCount(counts.substitutes) },
    { label: MENU.rail.noSubstitute, value: formatCount(counts.proofs) },
  ];

  return (
    <Panel
      id="menu"
      title={MENU.title}
      note={menu.caveat}
      actions={
        servesMealProgram ? (
          <span className={styles.links}>
            <Link href={`/artifacts/state-report?run=${runId}`}>{MENU.stateReportLink}</Link>
          </span>
        ) : null
      }
      printBlock
    >
      <StatRail items={items} className={styles.rail} />

      <p className={styles.note}>
        {cascadeCounts({
          brokenLines: menu.broken_items,
          brokenMeals: proposals.length,
          scheduledMeals: scheduledMealCount(rows),
          serviceDays: menu.dates.length,
          plannedMeals: formatCount(menu.planned_meals) ?? String(menu.planned_meals),
        })}
      </p>
      {menu.held_not_cascaded > 0 ? (
        <p className={styles.note}>{heldNotCascaded(menu.held_not_cascaded)}</p>
      ) : null}

      {rows.length === 0 ? (
        <>
          <p className={styles.statement}>{MENU.zeroCascade}</p>
          <p className={styles.note}>{MENU.zeroCascadeBody}</p>
        </>
      ) : (
        <div className={styles.tableBlock}>
          <h3 className={styles.subhead}>{MENU.brokenTitle}</h3>
          <DataTable<BrokenMeal>
            columns={mealColumns(menu.caveat)}
            rows={rows}
            rowKey={(row) => row.recipeId}
            caption={MENU.brokenCaption}
            className={styles.wideMeals}
            scroll
          />
        </div>
      )}

      {menu.entries.length > 0 ? (
        <div className={styles.tableBlock}>
          <h3 className={styles.subhead}>{MENU.itemsTitle}</h3>
          <DataTable<MenuEntry>
            columns={entryColumns(menu.caveat)}
            rows={menu.entries}
            rowKey={(entry) => entry.line.id}
            caption={MENU.itemsCaption}
            className={styles.wideEntries}
            scroll
          />
        </div>
      ) : null}

      <p className={styles.caveat}>{plannedTitle(menu.caveat)}</p>
    </Panel>
  );
}

/*
  One row per broken menu item. A recipe that is not on this week's menu still
  broke, so it keeps its row: the dates cell says it is not scheduled and the
  meal count is 0 rather than blank, because 0 planned meals is the true answer
*/
function mealColumns(caveat: string): Column<BrokenMeal>[] {
  return [
    {
      key: "meal",
      header: MENU.columns.meal,
      width: "260px",
      render: (row) => (
        <span className={styles.cellStack}>
          <span className={styles.strong}>{row.name}</span>
          <span className={styles.support}>
            <span className={styles.identifier}>{row.recipeId}</span>
            {row.provenance ? (
              <>
                {" "}
                <ProvenanceLabel provenance={row.provenance} />
              </>
            ) : null}
          </span>
        </span>
      ),
    },
    {
      key: "dates",
      header: MENU.columns.dates,
      width: "140px",
      groupEdge: true,
      render: (row) =>
        row.dates.length === 0 ? (
          <span className={styles.support}>{MENU.notScheduled}</span>
        ) : (
          <span className={styles.list}>
            {row.dates.map((date) => (
              <span className={`${styles.listItem} ${styles.dates}`} key={date}>
                {date}
              </span>
            ))}
          </span>
        ),
    },
    {
      key: "meals",
      header: MENU.columns.meals,
      variant: "measure",
      width: "132px",
      headerTitle: plannedTitle(caveat),
      render: (row) => <PlannedMeals count={row.plannedMeals} caveat={caveat} />,
    },
    {
      key: "broken_by",
      header: MENU.columns.brokenBy,
      groupEdge: true,
      render: (row) => (
        <span className={styles.list}>
          {row.brokenBy.map((entry) => (
            <span className={styles.listItem} key={entry.line.id}>
              <span className={styles.primary}>{entry.line.raw_description}</span>
              <span className={styles.support}>
                {[entry.line.storage_location, entry.line.lot_code ? `lot ${entry.line.lot_code}` : null]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </span>
          ))}
        </span>
      ),
    },
  ];
}

/*
  One row per pulled inventory line that reaches a recipe. This is the evidence
  under the table above: which case in which cooler, which recall named it, and
  whether a person has already cleared that pairing. A cleared line is not
*/
function entryColumns(caveat: string): Column<MenuEntry>[] {
  return [
    {
      key: "item",
      header: MENU.columns.item,
      width: "230px",
      render: (entry) => (
        <span className={styles.cellStack}>
          <span className={styles.strong}>{entry.line.raw_description}</span>
          <span className={styles.support}>{entry.line.normalized_description}</span>
        </span>
      ),
    },
    {
      key: "storage",
      header: MENU.columns.storage,
      width: "120px",
      render: (entry) => entry.line.storage_location ?? <NotRecorded />,
    },
    {
      key: "qty",
      header: MENU.columns.qty,
      variant: "measure",
      width: "84px",
      groupEdge: true,
      render: (entry) => formatQuantity(entry.line.quantity, entry.line.unit) ?? <NotRecorded />,
    },
    {
      key: "lot",
      header: MENU.columns.lot,
      variant: "identifier",
      width: "104px",
      render: (entry) => entry.line.lot_code ?? <NotRecorded />,
    },
    {
      key: "meals",
      header: MENU.columns.meals,
      variant: "measure",
      width: "124px",
      headerTitle: plannedTitle(caveat),
      render: (entry) => <PlannedMeals count={entry.planned_meals} caveat={entry.caveat} />,
    },
    {
      key: "appears_in",
      header: MENU.columns.appearsIn,
      width: "200px",
      groupEdge: true,
      render: (entry) => (
        <span className={styles.list}>
          {entry.recipes.map((recipe) => (
            <span className={styles.listItem} key={recipe.recipe_id}>
              <span className={styles.primary}>{recipe.name}</span>
              <span className={styles.support}>
                <span className={styles.identifier}>{recipe.recipe_id}</span>{" "}
                <ProvenanceLabel provenance={recipe.provenance} />
                {recipe.service_days.length === 0 ? ` · ${MENU.notScheduled}` : null}
              </span>
            </span>
          ))}
        </span>
      ),
    },
    {
      key: "recall",
      header: MENU.columns.recall,
      render: (entry) => (
        <span className={styles.list}>
          {entry.recalls.map((recall) => (
            <span className={styles.listItem} key={recall.match_id}>
              <span className={styles.primary}>
                <StatusBadge value={recall.status} /> <TierBadge tier={recall.tier} />{" "}
                {recall.recalling_firm ?? <NotRecorded />}
              </span>
              <span className={styles.support}>
                <span className={styles.identifier}>
                  {recall.source} {recall.source_record_id}
                </span>{" "}
                <ProvenanceLabel
                  provenance={recall.source_provenance}
                  label={recall.source_provenance_label}
                />{" "}
                {recall.classification ?? UNCLASSIFIED}
                {recall.recall_status !== "active" ? ` · recall ${recall.recall_status}` : null}
              </span>
              {recall.cleared_count > 0 ? (
                <span className={styles.support}>
                  <ClearedMark count={recall.cleared_count} />
                </span>
              ) : null}
            </span>
          ))}
        </span>
      ),
    },
  ];
}
