import { Facts, Kv, Note, PageHero, Pill, TabCard } from "@/components";
import { getSources, getStatus } from "@/lib/api";
import { channelLabel } from "@/lib/strings";
import { formatCount, formatDate } from "@/lib/format";
import { plural } from "@/lib/format";
import { UploadPanel } from "./UploadPanel";
import styles from "./ingest.module.css";

/*
  The ways an export reaches this location, and what to do when the scheduled
  one does not arrive. The list of ways is the API's, not a copy of it: an
  adapter added to the server appears here without anyone editing this file.
*/

export const dynamic = "force-dynamic";

export default async function AddInventoryPage() {
  const [statusResult, sourcesResult] = await Promise.all([getStatus(), getSources()]);
  const status = statusResult.ok ? statusResult.data : null;
  const run = status?.run ?? null;
  const adapters = sourcesResult.ok ? sourcesResult.data.adapters : [];

  return (
    <>
      {/* The figure is the run a new file would replace, because that is the
          thing a person is deciding about when they stand on this page. */}
      <PageHero
        figure={run ? `#${run.id}` : "0"}
        word={run ? "in force now" : "deliveries so far"}
        actions={run ? <Pill href="/sheet">Open sheet</Pill> : undefined}
      />

      {run ? (
        <Facts
          items={[
            { label: "channel", value: channelLabel(run.channel) },
            {
              label: "received",
              value: formatDate(run.business_date) ?? run.business_date,
            },
            { label: "rows read", value: formatCount(run.rows_read) ?? "0" },
            { label: "deliveries", value: formatCount(status?.run_count ?? 0) ?? "0" },
          ]}
        />
      ) : null}

      <UploadPanel />

      <TabCard
        title="Where inventory comes from"
        count={formatCount(adapters.length)}
        tone="sunken"
      >
        {adapters.length === 0 ? (
          <Note>The API did not answer, so the list of readers is not shown.</Note>
        ) : (
          adapters.map((adapter) => (
            <Kv
              key={adapter.name}
              term={channelLabel(adapter.channel)}
              value={
                <>
                  {adapter.doc || "No description is declared for this reader."}
                  <span className={styles.path}>
                    {adapter.provenance_label} ·{" "}
                    {plural(adapter.declares.length, "field")} declared
                    {adapter.cannot.length > 0
                      ? ` · cannot read ${adapter.cannot.join(", ")}`
                      : ""}
                  </span>
                </>
              }
            />
          ))
        )}
      </TabCard>
    </>
  );
}
