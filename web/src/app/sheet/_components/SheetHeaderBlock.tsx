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

export interface SheetHeaderBlockProps {
  header: SheetHeader;
}

/*
  The header of the PRINTED artefact: which kitchen, which day, when this copy
  was generated, what corpus it was matched against, and the counts the run
  froze when it finalized.

  On paper this is a letterhead and it earns its 256px, because a sheet that
  leaves the office has to carry its own provenance. On screen it does not: the
  masthead, the status line and the stat rail have already said the location,
  the date, the run and the counts before this block renders, and repeating them
  costs a quarter of the viewport on the one page where rows are the point. So
  the block is print-only, and SheetView renders a one-line screen version of
  the facts that are not already above it -- the corpus and its provenance.

  The corpus block is the load-bearing part. For the current run it lists each
  snapshot with its provenance label and capture date. For a past run the API
  deliberately sends no snapshots and sends corpus_note instead, which is the
  frozen sentence naming the corpora that run actually used. Printing tonight's
  capture dates over yesterday's lines would make a document look sourced when
  it is not, so this component renders whichever one it was given and never
  substitutes the other.
*/

export function CorpusValue({ header }: { header: SheetHeader }) {
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

export function SheetHeaderBlock({ header }: SheetHeaderBlockProps) {
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
