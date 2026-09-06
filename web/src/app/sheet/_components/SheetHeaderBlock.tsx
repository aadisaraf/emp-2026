import { DefinitionList, NotRecorded, ProvenanceLabel, type DefinitionItem } from "@/components";
import type { SheetHeader } from "@/lib/api";
import { CHANNEL_LABEL } from "@/lib/strings";
import {
  formatCount,
  formatDateTime,
  formatHours,
  shortDeliveryRef,
} from "@/lib/format";
import styles from "./sheet.module.css";

/* The printed sheet's header: kitchen, day, corpus, and the frozen counts. */

function CorpusValue({ header }: { header: SheetHeader }) {
  if (header.corpora.length > 0) {
    return (
      <span className={styles.corpusList}>
        {header.corpora.map((snapshot) => (
          <span className={styles.corpusEntry} key={snapshot.source}>
            <span className={styles.source}>{snapshot.source}</span>{" "}
            <ProvenanceLabel
              provenance={snapshot.provenance}
              label={snapshot.provenance_label}
              capturedAt={snapshot.captured_at}
            />{" "}
            <span className={styles.age}>
              {formatCount(snapshot.record_count)} records, {formatHours(snapshot.age_hours)} old
            </span>
            {snapshot.stale ? <strong className={styles.staleWord}>(stale)</strong> : null}
          </span>
        ))}
      </span>
    );
  }

  if (header.corpus_note) {
    return <span className={styles.frozenCorpus}>{header.corpus_note}</span>;
  }

  return <NotRecorded word="no recall snapshot has been loaded" />;
}

export function SheetHeaderBlock({ header }: {
  header: SheetHeader;
}) {
  const run = header.run;

  const items: DefinitionItem[] = [
    {
      term: "Location",
      value: header.location.name,
      hint: header.location.operator,
    },
    {
      term: "Address",
      value: header.location.address,
      hint: header.location.contact,
    },
    {
      term: "Business date",
      value: run.business_date,
      hint: `inventory delivered by ${CHANNEL_LABEL[run.channel] ?? run.channel}`,
    },
    {
      term: "Run",
      value: `#${run.id}`,
      hint: shortDeliveryRef(run.delivery_ref) ?? <NotRecorded />,
    },
    {
      term: "Generated",
      value: formatDateTime(header.generated_at) ?? header.generated_at,
      hint: `${header.location.timezone_name}${
        header.is_current ? "" : ". This run is not the current one."
      }`,
    },
    {
      term: "Recall corpus",
      value: <CorpusValue header={header} />,
      hint: header.corpora.length === 0 && header.corpus_note
        ? "the corpus this run was matched against, frozen when it finalized"
        : undefined,
    },
    {
      term: "Lines",
      value: `${formatCount(run.pull_count)} to pull · ${formatCount(
        run.held_count,
      )} held · ${formatCount(run.match_count)} total`,
      hint: `frozen when run #${run.id} finalized. ${formatCount(
        header.counts.new_count,
      )} new since the previous run.`,
    },
  ];

  return (
    <div className={styles.headerBlock} data-print-block>
      <DefinitionList items={items} columns={2} />
    </div>
  );
}
