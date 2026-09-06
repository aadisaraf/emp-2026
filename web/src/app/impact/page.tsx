import { EmptyState, ErrorState, PageHeader, Panel, PrintButton } from "@/components";
import { getImpact } from "@/lib/api";
import {
  EMPTY_NO_MENU_PROGRAM,
  EMPTY_NO_RUNS,
  PAGE_TITLES,
  pullSheetSubtitle,
} from "@/lib/strings";
/*
  The impact page's own components. They live in ./_components rather than in
  the shared library because nothing else on the site renders a credit claim
  line, a cascade row or a substitution proof.
*/
import { MenuPanel } from "./_components/MenuPanel";
import { MoneyPanel } from "./_components/MoneyPanel";
import { ProvenancePanel } from "./_components/ProvenancePanel";
import { SubstitutionPanel } from "./_components/SubstitutionPanel";
import styles from "./_components/impact.module.css";
import { PRINT_LABEL } from "@/lib/nav";

/* Impact: what the pulls cost, and what came off the menu. */

export const dynamic = "force-dynamic";

export default async function ImpactPage() {
  const result = await getImpact();

  if (!result.ok) {
    // No ok run has ever existed. That is not a clear result, and it is not an
    // empty page either: it is the statement that nothing has been compared.
    return (
      <>
        <PageHeader title={PAGE_TITLES.impact} />
        {result.error.code === "no_inventory" ? (
          <EmptyState
            heading={EMPTY_NO_RUNS.heading}
            body={EMPTY_NO_RUNS.body}
            action={EMPTY_NO_RUNS.action}
          />
        ) : (
          <ErrorState failure={result.error} />
        )}
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
