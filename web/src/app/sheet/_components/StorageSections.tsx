import { Chip, ChipRow, TabCard, ui } from "@/components";
import type { SheetLine, SheetSection } from "@/lib/api";
import { EVIDENCE_LABEL, NOT_RECORDED } from "@/lib/strings";
import { formatQuantity } from "@/lib/format";
import { cx } from "@/lib/cx";

export interface StorageSectionsProps {
  sections: SheetSection[];
}

const ROMAN: Record<1 | 2 | 3, string> = { 1: "I", 2: "II", 3: "III" };

/** The anchor a jump pill and a section head agree on. */
export function locationId(storage: string): string {
  return `loc-${storage.replace(/\s+/g, "-")}`;
}

/*
  Where the case is, then what it is, then why. Storage location is the only
  grouping on this sheet, because it is the walking order through the kitchen.
*/

function LineRow({ line }: { line: SheetLine }) {
  const firm = line.recalling_firm ?? line.source;

  return (
    <tr id={`match-${line.id}`}>
      <td>
        <button type="button" className={ui.open} data-match-id={line.id}>
          <span className={ui.lead}>{line.raw_description}</span>
          <span className={ui.sub}>
            Class {ROMAN[line.class_rank]} · {firm} · {line.source_record_id}
          </span>
        </button>
      </td>
      <td className={ui.num}>{formatQuantity(line.quantity, line.unit) ?? "—"}</td>
      <td className={ui.optSm}>
        <span className={cx(ui.mono, ui.lead)}>{line.lot_code ?? NOT_RECORDED}</span>
      </td>
      <td className={cx(ui.opt, ui.wrap)}>
        <span className={ui.sub}>{EVIDENCE_LABEL[line.evidence_kind] ?? line.evidence_kind}</span>
      </td>
      <td>
        <ChipRow>
          <Chip tone={line.status === "PULL" ? "pull" : "held"}>{line.status}</Chip>
          <Chip tone="quiet">{line.tier}</Chip>
          {line.is_new ? <Chip tone="quiet">new</Chip> : null}
          {line.recall_status === "amended" ? <Chip tone="quiet">amended</Chip> : null}
        </ChipRow>
      </td>
      <td className={ui.optSm}>
        {line.cleared ? (
          <Chip tone="done">recorded</Chip>
        ) : null}
      </td>
    </tr>
  );
}

export function StorageSections({ sections }: StorageSectionsProps) {
  return (
    <>
      {sections.map((section) => (
        <TabCard
          key={section.storage_location}
          id={locationId(section.storage_location)}
          title={section.storage_location}
          count={`${section.pull} pull · ${section.held} held`}
          flush
        >
          <table className={ui.rec} data-sheet="true">
            <caption>
              {section.storage_location}: {section.pull} PULL, {section.held} HELD,{" "}
              {section.cleared} recorded.
            </caption>
            <colgroup>
              <col />
              <col style={{ width: "90px" }} />
              <col className={ui.optSm} style={{ width: "110px" }} />
              <col className={ui.opt} style={{ width: "120px" }} />
              <col style={{ width: "175px" }} />
              <col className={ui.optSm} style={{ width: "110px" }} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col" className={ui.num}>
                  Qty
                </th>
                <th scope="col" className={ui.optSm}>
                  Lot
                </th>
                <th scope="col" className={ui.opt}>
                  Evidence
                </th>
                <th scope="col">Status</th>
                <th scope="col" className={ui.optSm}>
                  Recorded
                </th>
              </tr>
            </thead>
            <tbody>
              {section.lines.map((line) => (
                <LineRow key={line.id} line={line} />
              ))}
            </tbody>
          </table>
        </TabCard>
      ))}
    </>
  );
}
