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

/*
  Impact: what the pulls cost, and what came off the menu.

  The page is two halves and they are deliberately not merged. The money applies
  to every deployment, school or restaurant, and is always shown. The menu
  cascade exists only where the location runs a meal program; on a restaurant
  deployment it is one sentence saying so, not an empty panel dressed up as a
  feature that is coming.

  Three claims this page has to keep straight, because getting any of them wrong
  would put a number on a document that goes to a distributor or a state agency:

  1. Nothing is estimated. A pulled line the export did not price has no
     extended value, is named as excluded, and keeps its quantity.
  2. Every meal figure is a planning figure. None of them counts a meal that was
     served, and the word travels with the number.
  3. "No substitute" is a proof and not a failed search. It names the
     meal-pattern component no clean recipe in this kitchen supplies and how
     many candidates were tested to establish it.

  Impact always reads the latest ok run. There is no run parameter here, and the
  Jinja route does not take one either.
*/

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
