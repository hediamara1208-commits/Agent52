import { useRef } from "react";
import type { Exhibit } from "../model/sessionView";
import { useFocusScroll } from "./useFocusScroll";
import { newsDate, safeUrl } from "../friendly/NewsCards";

const WEB_METRIC = "web_news";

interface WebValue { title?: string; url?: string; source?: string; published?: string; snippet?: string }

function fmt(v: Exhibit["value"]): string {
  if (typeof v === "number") return Math.abs(v) <= 1.5 ? `${(v * 100).toFixed(2)}%` : v.toLocaleString();
  return JSON.stringify(v);
}

/** A Web Exhibit shows its article (title link, source, date, snippet), not raw JSON. */
function WebValueRows({ value, query }: { value: WebValue; query?: string }) {
  const href = safeUrl(value.url);
  return (
    <>
      <dt>Article</dt>
      <dd data-testid="web-exhibit-title">
        {href ? <a href={href} target="_blank" rel="noopener noreferrer nofollow">{value.title ?? href}</a> : value.title}
      </dd>
      {value.source && (<><dt>Source</dt><dd>{value.source}</dd></>)}
      {value.published && (<><dt>Published</dt><dd>{newsDate(value.published)}</dd></>)}
      {value.snippet && (<><dt>Snippet</dt><dd>{value.snippet}</dd></>)}
      {query && (<><dt>Search query</dt><dd><code>{query}</code></dd></>)}
      <dt>Confidence</dt><dd><span className="badge-context">Context</span> never changes a number or a rule</dd>
    </>
  );
}

function queryOf(exhibit: Exhibit): string | undefined {
  const q = (exhibit.inputs as { query?: unknown } | undefined)?.query;
  return typeof q === "string" ? q : undefined;
}

function ExhibitItem({ exhibit, focused, onFocus }: { exhibit: Exhibit; focused: boolean; onFocus: (n: number) => void }) {
  const ref = useRef<HTMLLIElement>(null);
  useFocusScroll(ref, focused);
  return (
    <li ref={ref} data-testid={`exhibit-${exhibit.number}`} data-focused={focused}>
      <button type="button" aria-expanded={focused} onClick={() => onFocus(exhibit.number)}>
        <span><span className="num">#{exhibit.number}</span> {exhibit.metric.replace(/_/g, " ")}</span>
        <span style={{ color: "var(--muted)" }}>{(exhibit.assets ?? []).slice(0, 3).join(", ")}</span>
      </button>
      {focused && (
        <dl data-testid={`exhibit-details-${exhibit.number}`}>
          {exhibit.metric === WEB_METRIC ? <WebValueRows value={exhibit.value as WebValue} query={queryOf(exhibit)} /> : (
            <><dt>Value</dt><dd><code>{fmt(exhibit.value)}</code> {exhibit.currency}</dd></>
          )}
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

function counts(exhibits: Exhibit[]): string {
  const web = exhibits.filter((e) => e.metric === WEB_METRIC).length;
  const code = exhibits.length - web;
  return web ? `${code} computed by code · ${web} news` : `${code} computed by code`;
}

/** Exhibit browser; the focused Exhibit opens its details, including Snapshot_Id (Req. 7.6, 7.17). */
export function ExhibitList({ exhibits, focusedNumber, onFocus }: {
  exhibits: Exhibit[]; focusedNumber: number | null; onFocus: (n: number) => void;
}) {
  return (
    <section aria-label="Exhibits">
      <div className="section-title"><h2>Exhibits</h2><span className="pill">{counts(exhibits)}</span></div>
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
