import { FSIS_NOTE, PAGE_TITLES, PRINT_LABEL, PROVENANCE_EXPLANATION, PROVENANCE_LEGEND, channelLabel } from "@/lib/strings";
import type {
  AdapterInfo,
  CorpusSnapshot,
  Provenance,
  SourceRef,
  SourcesResponse,
} from "@/lib/api";
import { getSources } from "@/lib/api";
import {
  DataTable,
  ErrorState,
  NotRecorded,
  PageHeader,
  Panel,
  PrintButton,
  ProvenanceLabel,
  type Column,
} from "@/components";
import { formatCount, formatDateTime, formatHours, unslug } from "@/lib/format";
import { RefreshControl } from "./RefreshControl";
import styles from "./sources.module.css";

/* Where every number comes from. */

export const dynamic = "force-dynamic";

const LABEL_ORDER: Provenance[] = ["live", "dated-snapshot", "hand-authored"];

export default async function SourcesPage() {
  const result = await getSources();

  if (!result.ok) {
    return (
      <>
        <PageHeader title={PAGE_TITLES.sources} />
        <ErrorState failure={result.error} />
      </>
    );
  }

  const data = result.data;
  const generated = formatDateTime(data.generated_at) ?? data.generated_at;
  const authored = data.sources.filter(
    (source) => source.provenance === "hand-authored",
  ).length;

  return (
    <>
      <PageHeader
        title={PAGE_TITLES.sources}
        context={`${data.location.name} · generated ${generated}`}
        actions={<PrintButton label={PRINT_LABEL["/sources"]} />}
      />

      <div className={styles.sections}>
        <Panel
          title="Three labels, and only three"
          note="Every source in this application carries exactly one of them, on screen and in print."
          printBlock
        >
          <dl className={styles.legend}>
            {LABEL_ORDER.map((provenance) => (
              <div key={provenance} style={{ display: "contents" }}>
                <dt>
                  <ProvenanceLabel
                    provenance={provenance}
                    label={data.labels[provenance]}
                  />
                </dt>
                <dd className={styles.legendValue}>
                  {PROVENANCE_EXPLANATION[provenance]}
                </dd>
              </div>
            ))}
          </dl>
          <p className={styles.legendNote}>{PROVENANCE_LEGEND}</p>
        </Panel>

        <Panel
          title="What was written rather than fetched"
          note={`${formatCount(authored)} of the ${formatCount(data.sources.length)} sources this build reads are hand-authored.`}
          printBlock
        >
          <div className={styles.stack}>
            <div className={styles.declaration}>
              <p className={styles.declarationHead}>USDA FSIS recall records</p>
              <p className={styles.declarationBody}>{FSIS_NOTE}</p>
            </div>
            <div className={styles.declaration}>
              <p className={styles.declarationHead}>The email delivery channel</p>
              <p className={styles.declarationBody}>
                The email_drop channel reads a committed mailbox file in the repository.
                There is no IMAP connection, no mailbox credential and no polling of a
                mail server, so the channel is labelled hand-authored wherever it appears
                rather than described as working mail.
              </p>
            </div>
            <p className={styles.prose}>
              The inventory fixture, the unit costs, the recipes and the meal-pattern
              components are hand-authored too, and each says so in the table at the foot
              of this page with the path to the file it lives in.
            </p>
          </div>
        </Panel>

        <Panel
          title="Recall corpora"
          note="What the inventory is compared against, and how old it is."
          flush
          printBlock
        >
          <DataTable<CorpusSnapshot>
            columns={CORPUS_COLUMNS}
            rows={data.snapshots}
            rowKey={(snapshot) => snapshot.source}
            caption="Recall corpora loaded in this build"
            empty="No recall snapshot has been loaded, so no inventory line has been compared against anything."
          />
        </Panel>

        <Panel
          title="Refresh the corpus"
          note="Try the agency, fall back to the committed snapshot, and say which happened."
          printBlock
        >
          <RefreshControl />
        </Panel>

        <Panel
          title="Delivery channels"
          note="How an inventory export reaches this location."
          flush
          printBlock
        >
          <DataTable<AdapterInfo>
            columns={adapterColumns(data.declarable.length)}
            rows={data.adapters}
            rowKey={(adapter) => adapter.name}
            caption="Ingestion adapters and their declared coverage"
          />
        </Panel>

        <Panel
          title="What each channel can read"
          note="Read from the ingestion code itself, so this table cannot fall out of step with what actually gets read."
          flush
          printBlock
        >
          <DataTable<string>
            columns={coverageColumns(data.adapters)}
            rows={data.declarable}
            rowKey={(field) => field}
            caption="Field coverage per delivery channel"
          />
        </Panel>

        <Panel printBlock>
          <p className={styles.prose}>
            <span className={styles.proseStrong}>{coverageSentence(data)}</span> A field
            marked cannot always comes back empty from that channel, and an empty field is
            not a zero: 50 of the 56 rows in the committed export carry no barcode and 11
            carry no lot code, which is why the sheet writes not recorded rather than
            leaving a cell blank.
          </p>
        </Panel>

        <Panel
          title="Every file this build reads"
          note="The key, the label, the path in the repository, and what it is."
          flush
          printBlock
        >
          <DataTable<SourceRef>
            columns={SOURCE_COLUMNS}
            rows={data.sources}
            rowKey={(source) => source.key}
            caption="Every source file, with its provenance label"
          />
        </Panel>

        <Panel
          title="Screening rule in force"
          note="What the matcher never compared, stated so the gap is visible."
          printBlock
        >
          <p className={styles.rule}>{data.screening_rule}</p>
        </Panel>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------------
   Corpora
--------------------------------------------------------------------------- */

const CORPUS_COLUMNS: Column<CorpusSnapshot>[] = [
  {
    key: "source",
    header: "Source",
    width: "120px",
    render: (snapshot) => <span className={styles.key}>{snapshot.source}</span>,
  },
  {
    key: "provenance",
    header: "Provenance",
    width: "160px",
    render: (snapshot) => (
      <ProvenanceLabel
        provenance={snapshot.provenance}
        label={snapshot.provenance_label}
      />
    ),
  },
  {
    key: "captured",
    header: "Captured",
    width: "160px",
    render: (snapshot) =>
      formatDateTime(snapshot.captured_at) ?? snapshot.captured_at,
  },
  {
    key: "age",
    header: "Age",
    variant: "measure",
    width: "110px",
    render: (snapshot) => (
      <span className={snapshot.stale ? styles.stale : styles.fresh}>
        {formatHours(snapshot.age_hours)}
        {snapshot.stale ? " stale" : ""}
      </span>
    ),
  },
  {
    key: "records",
    header: "Records",
    variant: "measure",
    width: "100px",
    render: (snapshot) => formatCount(snapshot.record_count),
  },
  {
    key: "fetch",
    header: "How it got here",
    width: "160px",
    groupEdge: true,
    render: (snapshot) => unslug(snapshot.fetch_status),
  },
];

/* ---------------------------------------------------------------------------
   Adapters
--------------------------------------------------------------------------- */

function adapterColumns(declarable: number): Column<AdapterInfo>[] {
  return [
    {
      key: "name",
      header: "Channel",
      width: "180px",
      render: (adapter) => (
        <>
          <span className={styles.key}>{adapter.name}</span>
          <span className={styles.fine}>{channelLabel(adapter.channel)}</span>
        </>
      ),
    },
    {
      key: "provenance",
      header: "Provenance",
      width: "160px",
      render: (adapter) => (
        <ProvenanceLabel
          provenance={adapter.provenance}
          label={adapter.provenance_label}
        />
      ),
    },
    {
      key: "reads",
      header: "Reads",
      variant: "measure",
      width: "110px",
      render: (adapter) => `${adapter.declares.length} of ${declarable}`,
    },
    {
      key: "cannot",
      header: "Cannot read",
      width: "260px",
      groupEdge: true,
      render: (adapter) =>
        adapter.cannot.length === 0 ? (
          <span className={styles.fresh}>reads every field</span>
        ) : (
          <span className={styles.cannot}>{adapter.cannot.join(", ")}</span>
        ),
    },
    {
      key: "doc",
      header: "What it is",
      render: (adapter) =>
        adapter.doc ? (
          <span className={styles.what}>{adapter.doc}</span>
        ) : (
          <NotRecorded word="this channel describes itself nowhere" />
        ),
    },
  ];
}

/* ---------------------------------------------------------------------------
   The coverage map: one row per declarable field, one column per channel.
--------------------------------------------------------------------------- */

function coverageColumns(adapters: AdapterInfo[]): Column<string>[] {
  return [
    {
      key: "field",
      header: "Inventory field",
      width: "260px",
      render: (field) => <span className={styles.key}>{field}</span>,
    },
    ...adapters.map<Column<string>>((adapter, index) => ({
      key: adapter.name,
      header: channelLabel(adapter.channel),
      width: "180px",
      groupEdge: index === 0,
      render: (field) =>
        adapter.declares.includes(field) ? (
          <span className={styles.reads}>reads</span>
        ) : (
          <span className={styles.cannot}>cannot</span>
        ),
    })),
  ];
}

function coverageSentence(data: SourcesResponse): string {
  const complete = data.adapters.filter((adapter) => adapter.cannot.length === 0).length;
  const lead =
    complete === data.adapters.length
      ? `All ${data.adapters.length}`
      : `${complete} of ${data.adapters.length}`;
  return `${lead} channels declare all ${data.declarable.length} fields.`;
}

/* ---------------------------------------------------------------------------
   Files
--------------------------------------------------------------------------- */

const SOURCE_COLUMNS: Column<SourceRef>[] = [
  {
    key: "key",
    header: "Source",
    width: "180px",
    render: (source) => <span className={styles.key}>{source.key}</span>,
  },
  {
    key: "provenance",
    header: "Provenance",
    width: "160px",
    render: (source) => (
      <ProvenanceLabel provenance={source.provenance} label={source.provenance_label} />
    ),
  },
  {
    key: "path",
    header: "File",
    width: "320px",
    groupEdge: true,
    render: (source) => <span className={styles.path}>{source.path}</span>,
  },
  {
    key: "what",
    header: "What it is",
    render: (source) => <span className={styles.what}>{source.description}</span>,
  },
];
