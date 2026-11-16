import { useRef } from "react";
import type { Exhibit } from "../model/sessionView";
import { useFocusScroll } from "./useFocusScroll";
import { ExhibitCard, exhibitTitle } from "./ExhibitCard";

const WEB_METRIC = "web_news";


function ExhibitItem({ exhibit, focused, onFocus }: { exhibit: Exhibit; focused: boolean; onFocus: (n: number) => void }) {
  const ref = useRef<HTMLLIElement>(null);
  useFocusScroll(ref, focused);
  return (
    <li ref={ref} data-testid={`exhibit-${exhibit.number}`} data-focused={focused}>
      <button type="button" aria-expanded={focused} onClick={() => onFocus(exhibit.number)}>
        <span><span className="num">#{exhibit.number}</span> {exhibitTitle(exhibit)}</span>
        <span style={{ color: "var(--muted)" }}>{(exhibit.assets ?? []).slice(0, 3).join(", ")}</span>
      </button>
      {focused && <ExhibitCard exhibit={exhibit} />}
    </li>
  );
}

function counts(exhibits: Exhibit[]): string {
  const web = exhibits.filter((e) => e.metric === WEB_METRIC).length;
  const code = exhibits.length - web;
  return web ? `${code} calculations · ${web} news` : `${code} calculations`;
}

/** Exhibit browser; the focused Exhibit opens its details, including Snapshot_Id (Req. 7.6, 7.17). */
export function ExhibitList({ exhibits, focusedNumber, onFocus }: {
  exhibits: Exhibit[]; focusedNumber: number | null; onFocus: (n: number) => void;
}) {
  return (
    <section aria-label="Exhibits">
      <div className="section-title"><h2>Evidence</h2><span className="pill">{counts(exhibits)}</span></div>
      {exhibits.length === 0 ? <p style={{ color: "var(--muted)" }}>No Exhibits yet.</p> : (
        <ul className="exhibit-grid">
          {exhibits.map((e) => (
            <ExhibitItem key={e.number} exhibit={e} focused={e.number === focusedNumber} onFocus={onFocus} />
          ))}
        </ul>
      )}
    </section>
  );
}
