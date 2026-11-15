import { useRef } from "react";
import type { Exhibit } from "../model/sessionView";
import { useFocusScroll } from "./useFocusScroll";

function fmt(v: Exhibit["value"]): string {
  return typeof v === "number" ? String(v) : JSON.stringify(v);
}

function ExhibitItem({ exhibit, focused, onFocus }: { exhibit: Exhibit; focused: boolean; onFocus: (n: number) => void }) {
  const ref = useRef<HTMLLIElement>(null);
  useFocusScroll(ref, focused);
  return (
    <li ref={ref} data-testid={`exhibit-${exhibit.number}`} data-focused={focused}>
      <button type="button" aria-expanded={focused} onClick={() => onFocus(exhibit.number)}>
        Exhibit {exhibit.number}: {exhibit.metric}
      </button>
      {focused && (
        <dl data-testid={`exhibit-details-${exhibit.number}`}>
          <dt>Value</dt><dd>{fmt(exhibit.value)} {exhibit.currency}</dd>
          <dt>Snapshot_Id</dt><dd data-testid="exhibit-snapshot-id">{exhibit.snapshot_id ?? "none"}</dd>
          {exhibit.period_start && (<><dt>Period</dt><dd>{exhibit.period_start} to {exhibit.period_end}</dd></>)}
          {exhibit.assets && exhibit.assets.length > 0 && (<><dt>Assets</dt><dd>{exhibit.assets.join(", ")}</dd></>)}
          {exhibit.source_files && exhibit.source_files.length > 0 && (<><dt>Source files</dt><dd>{exhibit.source_files.join(", ")}</dd></>)}
          {exhibit.processing_notes && exhibit.processing_notes.length > 0 && (<><dt>Processing notes</dt><dd>{exhibit.processing_notes.join("; ")}</dd></>)}
          {exhibit.snapshot_retrieved_at && (<><dt>Retrieved at</dt><dd>{exhibit.snapshot_retrieved_at}</dd></>)}
        </dl>
      )}
    </li>
  );
}

/** Exhibit list; the focused Exhibit opens its details, including Snapshot_Id (Req. 7.6, 7.17). */
export function ExhibitList({ exhibits, focusedNumber, onFocus }: {
  exhibits: Exhibit[]; focusedNumber: number | null; onFocus: (n: number) => void;
}) {
  return (
    <section aria-label="Exhibits">
      <h2>Exhibits</h2>
      {exhibits.length === 0 ? <p>No Exhibits yet.</p> : (
        <ul>
          {exhibits.map((e) => (
            <ExhibitItem key={e.number} exhibit={e} focused={e.number === focusedNumber} onFocus={onFocus} />
          ))}
        </ul>
      )}
    </section>
  );
}
