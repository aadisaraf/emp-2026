import {
  Body,
  Chip,
  EmptyState,
  ErrorState,
  Facts,
  Kv,
  KvSplit,
  Main,
  Note,
  PageHero,
  Pill,
  Rail,
  TabCard,
  Tag,
  ui,
} from "@/components";
import { getImpact } from "@/lib/api";
import { EMPTY_NO_RUNS, PAGE_TITLES } from "@/lib/strings";
import { formatCount, formatDate, formatMoney, formatQuantity } from "@/lib/format";
import { cx } from "@/lib/cx";
import type { ClaimLine, CorpusSnapshot, MenuProposal, MenuSummary } from "@/lib/types";

/* Impact: what the pulls cost, and what came off the menu. */

export const dynamic = "force-dynamic";

/** "Prairie Line Beef LLC · FSIS-RC-019-2026 +2". Provenance rides every line. */
function recallSummary(line: ClaimLine): string | null {
  const first = line.recalls[0];
  if (!first) return null;
  const firm = first.recalling_firm ?? first.source;
  const rest = line.recalls.length - 1;
  return `${firm} · ${first.source_record_id}${rest > 0 ? ` +${rest}` : ""}`;
}

function ClaimRow({ line }: { line: ClaimLine }) {
  const excluded = line.excluded_because !== null;
  const recalls = recallSummary(line);
  return (
    <tr>
      <td>
        <span className={ui.lead}>{line.raw_description}</span>
        {recalls ? <span className={ui.sub}>{recalls}</span> : null}
        {excluded ? (
          <span className={cx(ui.sub, ui.subAttend)}>{line.excluded_because}</span>
        ) : null}
      </td>
      <td className={ui.opt}>
        <span className={ui.sub}>{line.storage_location ?? "—"}</span>
      </td>
      <td className={ui.num}>{formatQuantity(line.quantity, line.unit) ?? "—"}</td>
      <td className={cx(ui.num, ui.optSm)}>{formatMoney(line.unit_cost) ?? "—"}</td>
      <td className={ui.num}>
        {excluded ? (
          <Chip tone="held">excluded</Chip>
        ) : (
          (formatMoney(line.extended) ?? "—")
        )}
      </td>
    </tr>
  );
}

function MenuCard({ menu }: { menu: MenuSummary }) {
  return (
    <TabCard title="Menu" tone="accent">
      <KvSplit term="Planned meals" value={formatCount(menu.planned_meals) ?? "0"} />
      <KvSplit term="Broken items" value={formatCount(menu.broken_items) ?? "0"} />
      <KvSplit term="Recipes affected" value={formatCount(menu.recipes) ?? "0"} />
      <KvSplit term="Held, not cascaded" value={formatCount(menu.held_not_cascaded) ?? "0"} />
      <Note>{menu.caveat}</Note>
    </TabCard>
  );
}

function ProposalItem({ proposal }: { proposal: MenuProposal }) {
  if (proposal.kind === "substitute") {
    return (
      <Kv
        term={proposal.broken_recipe}
        value={
          <>
            {proposal.name}
            {proposal.alternatives.length > 0 ? (
              <span className={ui.sub}>
                {formatCount(proposal.alternatives.length)} other candidates cover it
              </span>
            ) : null}
          </>
        }
      />
    );
  }
  return (
    <Kv
      term={proposal.broken_recipe}
      value={
        <>
          <Chip tone="held">no substitute</Chip>
          <span className={ui.sub}>
            {formatCount(proposal.candidates_checked)} checked · unmet: {proposal.unmet.join(", ")}
          </span>
        </>
      }
    />
  );
}

function SourcesCard({
  corpora,
  corpusNote,
}: {
  corpora: CorpusSnapshot[];
  corpusNote: string | null;
}) {
  return (
    <TabCard title="Sources" tone="sunken">
      {corpora.map((c) => (
        <KvSplit
          key={c.source}
          term={`${c.source} · ${c.provenance_label}`}
          value={
            <span className={c.stale ? ui.subAttend : undefined}>
              {formatCount(c.record_count)}
            </span>
          }
        />
      ))}
      {corpusNote ? <Note>{corpusNote}</Note> : null}
    </TabCard>
  );
}

export default async function ImpactPage() {
  const result = await getImpact();

  if (!result.ok) {
    // No ok run has ever existed. That is not a clear result, and it is not an
    // empty page either: it is the statement that nothing has been compared.
    if (result.error.code === "no_inventory") {
      return (
        <>
          <PageHero figure="0" word={PAGE_TITLES.impact} />
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
        <PageHero figure="—" word={PAGE_TITLES.impact} />
        <ErrorState failure={result.error} />
      </>
    );
  }

  const { run, header, claim, menu, proposals } = result.data;
  const excluded = claim.excluded.length;
  const vendors = claim.by_vendor.length;

  return (
    <>
      <PageHero
        figure={formatMoney(claim.total) ?? "—"}
        word="claimable"
        money
        actions={
          <>
            <Tag>run #{run.id}</Tag>
            <Pill href={`/artifacts/credit-claim?run=${run.id}`} tone="primary">
              Credit claim
            </Pill>
            <Pill href={`/artifacts/hold?run=${run.id}`}>Hold record</Pill>
          </>
        }
      />

      <Facts
        items={[
          { label: "pulled lines", value: formatCount(claim.lines.length) ?? "0" },
          { label: "priced", value: formatCount(claim.counted) ?? "0" },
          {
            label: "excluded",
            value: formatCount(excluded) ?? "0",
            tone: excluded > 0 ? "attend" : "plain",
          },
          { label: "vendors", value: formatCount(vendors) ?? "0" },
          { label: "inventory of", value: formatDate(run.business_date) ?? run.business_date },
        ]}
      />

      <Body>
        <Main>
          <TabCard
            title="Every pulled line"
            count={formatCount(claim.lines.length)}
            flush
          >
            <table className={ui.rec}>
              <caption>
                Every pulled line, in the order the claim produced it. A line the export did not
                price is marked excluded and left out of the total.
              </caption>
              <colgroup>
                <col />
                <col className={ui.opt} style={{ width: "130px" }} />
                <col style={{ width: "90px" }} />
                <col className={ui.optSm} style={{ width: "90px" }} />
                <col style={{ width: "110px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Item</th>
                  <th scope="col" className={ui.opt}>
                    Where
                  </th>
                  <th scope="col" className={ui.num}>
                    Qty
                  </th>
                  <th scope="col" className={cx(ui.num, ui.optSm)}>
                    Unit cost
                  </th>
                  <th scope="col" className={ui.num}>
                    Extended
                  </th>
                </tr>
              </thead>
              <tbody>
                {claim.lines.map((line) => (
                  <ClaimRow key={line.id} line={line} />
                ))}
              </tbody>
            </table>
          </TabCard>

          <Note>{claim.arithmetic}</Note>
        </Main>

        <Rail>
          <TabCard title="Vendors" count={formatCount(vendors)}>
            {claim.by_vendor.map((v) => (
              <KvSplit key={v.vendor} term={v.vendor} value={formatMoney(v.total) ?? "—"} />
            ))}
          </TabCard>

          {menu ? <MenuCard menu={menu} /> : null}

          {proposals.length > 0 ? (
            <TabCard title="Substitutions" count={formatCount(proposals.length)}>
              {proposals.map((p) => (
                <ProposalItem key={p.broken_recipe_id} proposal={p} />
              ))}
            </TabCard>
          ) : null}

          <SourcesCard corpora={header.corpora} corpusNote={header.corpus_note} />
        </Rail>
      </Body>
    </>
  );
}
