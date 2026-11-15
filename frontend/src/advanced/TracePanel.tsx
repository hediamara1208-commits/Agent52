import { useRef } from "react";
import type { TraceEvent } from "../model/sessionView";
import { useFocusScroll } from "./useFocusScroll";

const KIND_LABEL: Record<string, string> = {
  agent_call: "Agent call", tool_call: "Tool call", judge_check: "Judge check",
  guardrail_block: "Guardrail block", claim_removed: "Claim removed",
  snapshot_pinned: "Data event", cache_fallback: "Data event", ingestion_aborted: "Data event",
};

function summaryObject(s: TraceEvent["summary"]): Record<string, unknown> {
  return s && typeof s === "object" ? (s as Record<string, unknown>) : {};
}

function Entry({ ev, focused, onExhibit }: { ev: TraceEvent; focused: boolean; onExhibit: (n: number) => void }) {
  const ref = useRef<HTMLLIElement>(null);
  useFocusScroll(ref, focused);
  const obj = summaryObject(ev.summary);
  const hash = typeof obj.instruction_hash === "string" ? obj.instruction_hash : null;
  return (
    <li ref={ref} data-testid={`trace-${ev.seq}`} data-kind={ev.kind} data-focused={focused}>
      <strong>{KIND_LABEL[ev.kind] ?? ev.kind}</strong> {ev.name}
      {ev.timestamp ? <time> {ev.timestamp}</time> : null}
      {hash && <div>Instruction_Hash: <code data-testid="instruction-hash">{hash}</code></div>}
      {typeof ev.summary === "string" ? <div>{ev.summary}</div> : (
        <pre>{JSON.stringify(
          Object.fromEntries(Object.entries(obj).filter(([k]) => k !== "instruction_hash")), null, 1)}</pre>
      )}
      {ev.exhibit_number != null && (
        <button type="button" className="exhibit-link" onClick={() => onExhibit(ev.exhibit_number as number)}>
          [Exhibit {ev.exhibit_number}]
        </button>
      )}
    </li>
  );
}

/** Trace JSON download (Req. 7.7). Plain data URL, no network call. */
export function TraceDownload({ trace }: { trace: TraceEvent[] }) {
  const href = "data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(trace, null, 2));
  return <a href={href} download="trace.json" data-testid="trace-download">Download Trace JSON</a>;
}

/** Trace panel: agent calls with Instruction_Hash, tool calls, Judge checks, Guardrail blocks, data events. */
export function TracePanel({ trace, focusedSeq, onExhibit }: {
  trace: TraceEvent[]; focusedSeq: number | null; onExhibit: (n: number) => void;
}) {
  return (
    <section aria-label="Trace">
      <h2>Trace</h2>
      <TraceDownload trace={trace} />
      {trace.length === 0 ? <p>No trace entries yet.</p> : (
        <ol>{trace.map((ev) => <Entry key={ev.seq} ev={ev} focused={ev.seq === focusedSeq} onExhibit={onExhibit} />)}</ol>
      )}
    </section>
  );
}
