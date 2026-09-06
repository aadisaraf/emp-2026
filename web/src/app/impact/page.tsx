import { EmptyState, ErrorState, PageHeader, Panel, PrintButton } from "@/components";
import { attempt, getImpact } from "@/lib/api";
import {
  EMPTY_NO_MENU_PROGRAM,
  EMPTY_NO_RUNS,
  PAGE_TITLES,
  pullSheetSubtitle,
} from "@/lib/strings";
import { MenuPanel, MoneyPanel, ProvenancePanel, SubstitutionPanel } from "./_components";
import styles from "./_components/impact.module.css";
import { PRINT_LABEL } from "@/lib/nav";

/* Impact: what the pulls cost, and what came off the menu. */

export const dynamic = "force-dynamic";

export default async function ImpactPage() {
  const result = await attempt(getImpact());

  if (!result.ok) {
    // No ok run has ever existed. That is not a clear result, and it is not an
    // empty page either: it is the statement that nothing has been compared.
    if (result.error.code === "no_inventory") {
      return (
        <>
          <PageHeader title={PAGE_TITLES.impact} />
          <EmptyState
            heading={EMPTY_NO_RUNS.heading}
            body={EMPTY_NO_RUNS.body}
            action={EMPTY_NO_RUNS.action}
          />
        </>
      );
    }
    return (
      <>
        <PageHeader title={PAGE_TITLES.impact} />
        <ErrorState failure={result.error} />
      </>
    );
  }

  const impact = result.data;
  const { run, header, claim, menu, proposals } = impact;

  return (
    <>
      <PageHeader
        title={PAGE_TITLES.impact}
        context={pullSheetSubtitle(run.id, run.business_date)}
        actions={<PrintButton label={PRINT_LABEL["/impact"]} />}
      />

      <div className={styles.stack}>
        <MoneyPanel claim={claim} runId={run.id} />

        {menu ? (
          <>
            <MenuPanel
              menu={menu}
              proposals={proposals}
              runId={run.id}
              servesMealProgram={impact.serves_meal_program}
            />
            <SubstitutionPanel
              proposals={proposals}
              caveat={impact.components_caveat}
            />
          </>
        ) : (
          <Panel title={EMPTY_NO_MENU_PROGRAM.heading} printBlock>
            <p className={styles.note}>{EMPTY_NO_MENU_PROGRAM.body}</p>
          </Panel>
        )}

        <ProvenancePanel
          sources={claim.sources}
          corpora={header.corpora}
          corpusNote={header.corpus_note}
          menu={menu}
        />
      </div>
    </>
  );
}
