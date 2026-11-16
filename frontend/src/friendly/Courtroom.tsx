import { useEffect, useMemo, useRef, useState } from "react";
import type { SessionView } from "../model/sessionView";
import { courtState } from "./CourtroomScene";
import { ExhibitLink } from "./ExhibitLinks";
import { SPEAKER_NAME, hearingOf, type Speaker, type Speech } from "./hearing";

/** The members of the court: what each one does, and whether it is an AI agent or plain code. */
const CAST: Record<Exclude<Speaker, "objection">, { role: string; kind: string }> = {
  advocate: { role: "Argues for your goal", kind: "AI agent" },
  judge: { role: "Weighs both sides and rules", kind: "AI agent" },
  investigator: { role: "Examines the risks", kind: "AI agent" },
  bailiff: { role: "Checks your limits", kind: "Calculation" },
  clerk: { role: "Keeps the record", kind: "Calculation" },
};
const GLYPH: Record<keyof typeof CAST, string> = {
  judge: "M12 4v16M7 20h10M5 8h14M5 8l-3 6a3 3 0 0 0 6 0L5 8zm14 0l-3 6a3 3 0 0 0 6 0l-3-6z",
  advocate: "M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z",
  investigator: "M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13zm5 11.5L20 20",
  bailiff: "M5 6l2 2 3-3M5 13l2 2 3-3M13 7h6M13 14h6M5 19.5h14",
  clerk: "M7 3h7l4 4v14H7V3zm7 0v4h4M10 12h5M10 16h5",
};
const SEATS = ["advocate", "judge", "investigator", "bailiff", "clerk"] as const;

/** The phases of a hearing, in order, and which speeches belong to each. */
export const PHASES = ["Opening", "Defense", "Prosecutor", "Evidence check", "Ruling"] as const;
export function phaseOf(speeches: Speech[], index: number): number {
  const s = speeches[index];
  if (!s) return 0;
  if (s.speaker === "advocate") return 1;
  if (s.speaker === "investigator") return 2;
  if (s.speaker === "judge" || s.speaker === "clerk") return 4;
  if (s.speaker === "objection") return 3;
  return speeches.slice(0, index).some((x) => x.speaker === "advocate") ? 3 : 0; // bailiff
}

/** Pause before the Judge speaks, so the ruling lands. */
const ANTICIPATION_MS = 1600;

/** Characters per second for the typewriter; a pause between speeches. */
const CPS = 42;
const PAUSE_MS = 1300;

/** The courtroom: every member takes the floor in turn. Speeches come from the session's own
 * outputs (no model call). Plays live while the court sits, then replays the whole hearing. */
export function Courtroom({ view, onOpen }: {
  view: SessionView;
  onOpen: (n: number) => void;
}) {
  const running = view.status === "running";
  const speeches = useMemo(() => hearingOf(view), [view]);
  const { active: working, caption } = courtState(view.active_agent, running, view.stage, view.stages_done);
  const [index, setIndex] = useState(0);
  const [typed, setTyped] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [replaying, setReplaying] = useState(false);
  const [held, setHeld] = useState(false); // the hush before the Judge rules
  const seenCompleted = useRef(view.status === "completed");

  // Live: follow the latest speech. On completion: replay the whole hearing once.
  useEffect(() => {
    if (running && speeches.length) { setIndex(speeches.length - 1); setTyped(0); setPlaying(true); }
  }, [running, speeches.length]);
  useEffect(() => {
    if (view.status === "completed" && !seenCompleted.current) {
      seenCompleted.current = true; setIndex(0); setTyped(0); setPlaying(true); setReplaying(true);
    }
  }, [view.status]);

  const current = speeches[Math.min(index, speeches.length - 1)];
  const full = current?.text.length ?? 0;

  // Typewriter, then (when playing and not live) the next speech.
  useEffect(() => {
    if (!current || running || current.speaker !== "judge") { setHeld(false); return; }
    setHeld(true);
    const id = setTimeout(() => setHeld(false), ANTICIPATION_MS);
    return () => clearTimeout(id);
  }, [current?.id, running]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!current || held) return;
    if (typed < full) {
      const id = setTimeout(() => setTyped((t) => Math.min(full, t + 2)), 2000 / CPS);
      return () => clearTimeout(id);
    }
    if (!playing || index >= speeches.length - 1) return;
    const id = setTimeout(() => { setIndex((i) => i + 1); setTyped(0); }, PAUSE_MS);
    return () => clearTimeout(id);
  }, [typed, full, playing, index, speeches.length, current, held]);

  const speaker = current?.speaker;
  const finished = !running && index >= speeches.length - 1 && typed >= full;
  const talking = !!current && !held && typed < full;
  const onFloor = (agent: string) => speaker === agent || (speaker === "objection" && agent === "bailiff");
  const seatOn = (agent: string) => (running ? working === agent || (talking && onFloor(agent)) : onFloor(agent));
  const phase = running ? Math.min(4, ["request_rules", "advocate", "investigator", "judge"].filter((x) => view.stages_done.includes(x)).length)
    : phaseOf(speeches, index);
  const go = (i: number) => { setIndex(i); setTyped(0); setPlaying(false); };

  return (
    <section className="card hearing" aria-label="Courtroom">
      <ol className="phase-rail" aria-label="Phases of the hearing">
        {PHASES.map((p, i) => (
          <li key={p} data-state={i < phase ? "done" : i === phase ? "active" : "pending"}>{p}</li>
        ))}
      </ol>
      <div className={`bench${held ? " hush" : ""}`} role="group" aria-label="Members of the court">
        {SEATS.map((key) => {
          const on = seatOn(key);
          return (
            <div key={key} data-testid={`seat-${key}`} data-active={on ? "true" : "false"} className={`seat seat-${key}${on ? " seat-active" : ""}`}>
              <span className="avatar" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d={GLYPH[key]} /></svg>
              </span>
              <b>{SPEAKER_NAME[key]}</b>
              <small>{CAST[key].role}</small>
              <small className="kind">{CAST[key].kind}</small>
            </div>
          );
        })}
      </div>
      <div className="floor">
        {held && <p className="hush-line" data-testid="anticipation">The Judge is about to rule…</p>}
        {current && !held && (
          <div className={`speech speaker-${current.speaker}`} data-testid="speech-bubble" aria-live="polite">
            <strong>{current.speaker === "objection" ? "Statement removed" : SPEAKER_NAME[current.speaker]}</strong>
            {current.struck && <p className="struck">{current.struck}</p>}
            <p>{current.text.slice(0, typed)}<span className="caret" aria-hidden="true">{typed < full ? "▍" : ""}</span></p>
            {typed >= full && current.exhibits.length > 0 && (
              <p className="speech-evidence">{current.exhibits.map((n) => <ExhibitLink key={n} number={n} onOpen={onOpen} />)}</p>
            )}
          </div>
        )}
      </div>
      <div className="court-controls">
        <span className="court-caption"><span className="dot" />
          {!running && !finished && speeches.length > 1 ? "The hearing, replayed from the court record…" : caption}</span>
        <span className="court-buttons">
          <button type="button" disabled={running || index === 0} onClick={() => go(Math.max(0, index - 1))} aria-label="Previous speech">◀</button>
          <button type="button" disabled={running || !speeches.length} data-testid="replay"
            onClick={() => { if (finished) { setIndex(0); setTyped(0); setPlaying(true); setReplaying(true); } else setPlaying((p) => !p); }}>
            {finished ? "↻ Replay the hearing" : playing ? "❚❚ Pause" : "▶ Play"}
          </button>
          <button type="button" disabled={running || index >= speeches.length - 1} onClick={() => go(index + 1)} aria-label="Next speech">▶</button>
          <button type="button" disabled={running} onClick={() => go(Math.max(0, speeches.findIndex((s) => s.speaker === "judge")))}>Skip to verdict</button>
        </span>
      </div>
      {speeches.length > 0 && (
        <details className="court-record-wrap" open={finished || undefined}>
          <summary>Court record ({Math.min(index + 1, speeches.length)} of {speeches.length} statements)</summary>
          <ol className="court-record" aria-label="Court record" data-testid="court-record">
            {speeches.slice(0, index + 1).map((s, i) => (
              <li key={s.id} className={`record-${s.speaker}${i === index ? " current" : ""}`}>
                <button type="button" className="record-speaker" onClick={() => go(i)}>{SPEAKER_NAME[s.speaker]}</button>
                <span>
                  {s.struck && <del>{s.struck} </del>}
                  {s.text}{" "}
                  {s.exhibits.map((n) => <ExhibitLink key={n} number={n} onOpen={onOpen} />)}
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}
