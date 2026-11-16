import { useEffect, useMemo, useRef, useState } from "react";
import type { SessionView } from "../model/sessionView";
import { courtState } from "./CourtroomScene";
import { ExhibitLink } from "./ExhibitLinks";
import { SPEAKER_NAME, hearingOf, type Speaker, type Speech } from "./hearing";
import { Character, type Mood } from "./Characters";

/** Where each member stands in the 1200 x 560 scene (x, y = where the body meets the desk). */
const CAST: Record<Exclude<Speaker, "objection">, { x: number; y: number; trim: string; role: string; scale: number }> = {
  judge: { x: 600, y: 232, trim: "#e7b75f", role: "Weighs your preferences and rules", scale: 1 },
  advocate: { x: 250, y: 420, trim: "#4fd1e8", role: "Argues for your goal", scale: 1.05 },
  investigator: { x: 950, y: 420, trim: "#a99bff", role: "Examines the risks", scale: 1.05 },
  clerk: { x: 600, y: 440, trim: "#34d399", role: "Keeps the record", scale: 0.92 },
  bailiff: { x: 90, y: 330, trim: "#d6a756", role: "The code: checks your limits", scale: 0.85 },
};
const INVESTOR = { x: 1090, y: 330 };
const anchor = (s: Speaker) => (s === "objection" ? CAST.bailiff : CAST[s]);

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
  const gavel = speaker === "judge" && !held && typed >= full;
  const pos = speaker ? anchor(speaker) : null;
  // The camera moves to whoever has the floor, and pulls back when the hearing is over.
  const zoomed = !!pos && !finished && (talking || held);
  const camera = zoomed && pos
    ? { transform: `scale(${held ? 1.5 : 1.32})`, transformOrigin: `${Math.min(80, Math.max(20, (pos.x / 1200) * 100))}% ${((pos.y - 70) / 560) * 100}%` }
    : { transform: "scale(1)", transformOrigin: "50% 40%" };
  const mood = (agent: string): Mood =>
    held ? (agent === "judge" ? "stern" : "listening")
      : onFloor(agent) && talking ? "speaking"
      : speaker === "objection" && agent === "judge" ? "stern" : "idle";
  const phase = running ? Math.min(4, ["request_rules", "advocate", "investigator", "judge"].filter((x) => view.stages_done.includes(x)).length)
    : phaseOf(speeches, index);
  const go = (i: number) => { setIndex(i); setTyped(0); setPlaying(false); };

  return (
    <section className="card courtroom court-full" aria-label="Courtroom">
      <ol className="phase-rail" aria-label="Phases of the hearing">
        {PHASES.map((p, i) => (
          <li key={p} data-state={i < phase ? "done" : i === phase ? "active" : "pending"}>{p}</li>
        ))}
      </ol>
      <div className={`court-stage${held ? " hush" : ""}${speaker === "objection" && !running ? " objection" : ""}`}>
        <div className="court-view">
        <svg role="img" aria-label="Courtroom scene" viewBox="0 0 1200 560" width="100%" className="court-camera" style={camera}>
          <defs>
            <linearGradient id="cWall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2f4a3f" /><stop offset="1" stopColor="#1b2a24" /></linearGradient>
            <linearGradient id="cWood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#8a5a34" /><stop offset="1" stopColor="#56341c" /></linearGradient>
            <linearGradient id="cFloor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#24382f" /><stop offset="1" stopColor="#121c18" /></linearGradient>
            <radialGradient id="cLight" cx=".5" cy="0" r=".9"><stop offset="0" stopColor="#ffe3a3" stopOpacity=".3" /><stop offset="1" stopColor="#ffe3a3" stopOpacity="0" /></radialGradient>
          </defs>
          <rect width="1200" height="340" fill="url(#cWall)" />
          {/* tall windows and columns */}
          {[150, 370, 830, 1050].map((x) => (
            <g key={x}>
              <rect x={x - 46} y="40" width="92" height="210" rx="46" fill="#6f8f80" opacity=".28" />
              <path d={`M ${x} 40 L ${x} 250 M ${x - 46} 140 L ${x + 46} 140`} stroke="#1b2a24" strokeWidth="4" opacity=".6" />
            </g>
          ))}
          {[40, 260, 480, 720, 940, 1160].map((x) => <rect key={x} x={x - 12} y="0" width="24" height="340" fill="#22332b" />)}
          <circle cx="600" cy="62" r="38" fill="#1d2c25" stroke="#e7b75f" strokeWidth="3" />
          <text x="600" y="72" textAnchor="middle" fontSize="30">⚖</text>
          <rect y="340" width="1200" height="220" fill="url(#cFloor)" />
          <polygon className="spot" points="460,0 740,0 940,560 260,560" fill="url(#cLight)" />
          {/* the Judge sits behind the raised bench */}
          <g data-testid="seat-judge" data-active={seatOn("judge") ? "true" : "false"} className={`seat${seatOn("judge") ? " seat-active" : ""}`}
            transform={`translate(${CAST.judge.x} ${CAST.judge.y})`}>
            <Character who="judge" mood={mood("judge")} />
          </g>
          <rect x="380" y="232" width="440" height="108" rx="10" fill="url(#cWood)" stroke="#2a1a0e" strokeWidth="3" />
          <rect x="380" y="232" width="440" height="12" rx="6" fill="#e7b75f" />
          <text x="600" y="296" textAnchor="middle" fontSize="18" fontWeight="800" fill="#f6d58e" letterSpacing="5">JUDGE</text>
          <text x="600" y="318" textAnchor="middle" fontSize="12" fill="#e9d9b8" opacity=".85">{CAST.judge.role}</text>
          <g className={`gavel${gavel ? " strike" : ""}`} transform="translate(740 226)">
            <rect x="-4" y="-40" width="8" height="40" rx="3" fill="#8a5a2b" transform="rotate(-35)" />
            <rect x="-24" y="-54" width="34" height="18" rx="5" fill="#b9814a" stroke="#2a1a0e" strokeWidth="2" transform="rotate(-35)" />
          </g>
          {/* witness box with the investor */}
          <g transform={`translate(${INVESTOR.x} ${INVESTOR.y}) scale(.8)`}><Character who="investor" mood={held ? "listening" : "idle"} /></g>
          <rect x={INVESTOR.x - 62} y={INVESTOR.y - 4} width="124" height="62" rx="8" fill="url(#cWood)" stroke="#2a1a0e" strokeWidth="3" />
          <text x={INVESTOR.x} y={INVESTOR.y + 32} textAnchor="middle" fontSize="13" fontWeight="700" fill="#f6d58e">YOU</text>
          {(["bailiff", "advocate", "investigator", "clerk"] as const).map((key) => {
            const c = CAST[key];
            const on = seatOn(key);
            return (
              <g key={key} data-testid={`seat-${key}`} data-active={on ? "true" : "false"}
                className={`seat${on ? " seat-active" : ""}`} transform={`translate(${c.x} ${c.y})`}>
                <g transform={`scale(${c.scale})`}><Character who={key} mood={mood(key)} /></g>
                <rect x="-74" y="-4" width="148" height="56" rx="8" fill="url(#cWood)" stroke={on ? c.trim : "#2a1a0e"} strokeWidth="3" />
                <text x="0" y="22" textAnchor="middle" fontSize="15" fontWeight="800" fill={on ? c.trim : "#f6d58e"} letterSpacing="2">
                  {SPEAKER_NAME[key].toUpperCase()}
                </text>
                <text x="0" y="40" textAnchor="middle" fontSize="11" fill="#e9d9b8" opacity=".85">{c.role}</text>
              </g>
            );
          })}
          {/* gallery */}
          {Array.from({ length: 13 }, (_, i) => (
            <path key={i} d={`M ${40 + i * 92} 560 q 0 -42 30 -42 q 30 0 30 42 Z`} fill="#0c1410" opacity=".8" />
          ))}
        </svg>
        {speaker === "objection" && !running && <div className="objection-stamp" aria-hidden="true">Objection sustained</div>}
        </div>
        {held && <div className="hush-caption" data-testid="anticipation">The court falls silent. The Judge is about to rule…</div>}
        {current && !held && (
          <div className={`speech-bubble speaker-${current.speaker}`} data-testid="speech-bubble" aria-live="polite">
            <strong>{SPEAKER_NAME[current.speaker]}{current.speaker === "bailiff" || current.speaker === "objection" || current.speaker === "clerk" ? " · code" : " · AI agent"}</strong>
            {current.struck && <p className="struck">{current.struck}</p>}
            <p>{current.text.slice(0, typed)}<span className="caret" aria-hidden="true">{typed < full ? "▍" : ""}</span></p>
            {typed >= full && current.exhibits.length > 0 && (
              <p className="speech-evidence">Evidence: {current.exhibits.map((n) => <ExhibitLink key={n} number={n} onOpen={onOpen} />)}</p>
            )}
          </div>
        )}
      </div>
      <div className="court-controls">
        <span className="court-caption"><span className="dot" style={{ color: running ? "#e7b75f" : "#34d399" }} />
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
