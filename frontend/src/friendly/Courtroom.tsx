import { useEffect, useMemo, useRef, useState } from "react";
import type { SessionView } from "../model/sessionView";
import { courtState } from "./CourtroomScene";
import { ExhibitLink } from "./ExhibitLinks";
import { SPEAKER_NAME, hearingOf, type Speaker, type Speech } from "./hearing";

/** Where each member stands in the 1200 x 560 scene, and how they look. */
const CAST: Record<Exclude<Speaker, "objection">, { x: number; y: number; robe: string; trim: string; icon: string; role: string }> = {
  judge: { x: 600, y: 196, robe: "#141821", trim: "#e7b75f", icon: "🏛", role: "Weighs preferences, rules" },
  advocate: { x: 230, y: 410, robe: "#123447", trim: "#4fd1e8", icon: "⚖", role: "Pleads for the investor's goal" },
  investigator: { x: 970, y: 410, robe: "#2a2350", trim: "#8b7bff", icon: "🔎", role: "Names the risks" },
  clerk: { x: 600, y: 420, robe: "#123a2e", trim: "#34d399", icon: "📜", role: "Writes the ruling" },
  bailiff: { x: 80, y: 340, robe: "#3a2f1a", trim: "#d6a756", icon: "⚙", role: "The code: your limits" },
};
const INVESTOR = { x: 900, y: 252 };
const anchor = (s: Speaker) => (s === "objection" ? CAST.bailiff : CAST[s]);

/** Characters per second for the typewriter; a pause between speeches. */
const CPS = 42;
const PAUSE_MS = 1300;

function Person({ robe, trim, judge = false }: { robe: string; trim: string; judge?: boolean }) {
  return (
    <g className="person">
      <path d="M -34 0 Q -34 -46 0 -48 Q 34 -46 34 0 Z" fill={robe} stroke={trim} strokeOpacity=".55" />
      <path d="M -10 -46 L 0 -30 L 10 -46" fill="none" stroke={trim} strokeWidth="3" />
      <circle cx="0" cy="-66" r="17" fill="#e8c9a8" />
      {judge && <path d="M -19 -70 Q -20 -90 0 -88 Q 20 -90 19 -70 Q 22 -58 16 -52 L -16 -52 Q -22 -58 -19 -70 Z" fill="#f2efe6" opacity=".9" />}
      <circle className="mouth" cx="0" cy="-58" r="2.6" fill="#7a3b2e" />
    </g>
  );
}

/** The courtroom: every member takes the floor in turn. Speeches come from the session's own
 * outputs (no model call). Plays live while the court sits, then replays the whole hearing. */
export function Courtroom({ view, onOpen, speak }: {
  view: SessionView;
  onOpen: (n: number) => void;
  /** Optional voice: resolves when the speech's audio has finished. */
  speak?: (speech: Speech) => Promise<void>;
}) {
  const running = view.status === "running";
  const speeches = useMemo(() => hearingOf(view), [view]);
  const { active: working, caption } = courtState(view.active_agent, running, view.stage, view.stages_done);
  const [index, setIndex] = useState(0);
  const [typed, setTyped] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [voice, setVoice] = useState(false);
  const seenCompleted = useRef(view.status === "completed");

  // Live: follow the latest speech. On completion: replay the whole hearing once.
  useEffect(() => {
    if (running && speeches.length) { setIndex(speeches.length - 1); setTyped(0); setPlaying(true); }
  }, [running, speeches.length]);
  useEffect(() => {
    if (view.status === "completed" && !seenCompleted.current) {
      seenCompleted.current = true; setIndex(0); setTyped(0); setPlaying(true);
    }
  }, [view.status]);

  const current = speeches[Math.min(index, speeches.length - 1)];
  const full = current?.text.length ?? 0;

  // Typewriter, then (when playing and not live) the next speech.
  useEffect(() => {
    if (!current) return;
    if (typed < full) {
      const id = setTimeout(() => setTyped((t) => Math.min(full, t + 2)), 2000 / CPS);
      return () => clearTimeout(id);
    }
    if (!playing || index >= speeches.length - 1) return;
    const id = setTimeout(() => { setIndex((i) => i + 1); setTyped(0); }, PAUSE_MS);
    return () => clearTimeout(id);
  }, [typed, full, playing, index, speeches.length, current]);

  // Voice: start the speech's audio when it takes the floor (optional).
  useEffect(() => {
    if (voice && speak && current && playing) void speak(current).catch(() => undefined);
  }, [voice, speak, current?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const speaker = current?.speaker;
  const seatOn = (agent: string) => (running ? working === agent : speaker === agent || (speaker === "objection" && agent === "bailiff"));
  const gavel = speaker === "judge" && typed >= full;
  const pos = speaker ? anchor(speaker) : null;
  // The Judge's bubble sits to the right of the bench, so it never hides the Judge.
  const bubbleLeft = speaker === "judge" ? 57 : pos ? Math.min(Math.max(pos.x / 12 - 18, 1), 62) : 0;
  const bubbleTop = speaker === "judge" ? 3 : pos ? Math.max(pos.y / 5.6 - 50, 1) : 0;
  const finished = !running && index >= speeches.length - 1 && typed >= full;

  return (
    <section className="card courtroom court-full" aria-label="Courtroom">
      <div className="court-stage">
        <svg role="img" aria-label="Courtroom scene" viewBox="0 0 1200 560" width="100%">
          <defs>
            <linearGradient id="cWall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2a1d12" /><stop offset="1" stopColor="#140d07" /></linearGradient>
            <linearGradient id="cWood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#6b4426" /><stop offset="1" stopColor="#3a2414" /></linearGradient>
            <linearGradient id="cFloor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1b1410" /><stop offset="1" stopColor="#070504" /></linearGradient>
            <radialGradient id="cLight" cx=".5" cy="0" r=".9"><stop offset="0" stopColor="#ffe3a3" stopOpacity=".35" /><stop offset="1" stopColor="#ffe3a3" stopOpacity="0" /></radialGradient>
            <radialGradient id="cGlow" cx=".5" cy=".5" r=".5"><stop offset="0" stopColor="#f6d58e" stopOpacity=".55" /><stop offset="1" stopColor="#f6d58e" stopOpacity="0" /></radialGradient>
          </defs>
          {/* back wall, panels and seal */}
          <rect width="1200" height="330" fill="url(#cWall)" />
          {Array.from({ length: 10 }, (_, i) => (
            <rect key={i} x={20 + i * 118} y="30" width="96" height="230" rx="6" fill="none" stroke="#e7b75f" strokeOpacity=".09" />
          ))}
          <circle cx="600" cy="52" r="34" fill="#1d140b" stroke="#e7b75f" strokeOpacity=".7" strokeWidth="3" />
          <text x="600" y="58" textAnchor="middle" fontSize="22">⚖</text>
          <text x="600" y="104" textAnchor="middle" fontSize="10" fill="#f6d58e" letterSpacing="4" opacity=".8">DECISION TRIBUNAL</text>
          <rect y="330" width="1200" height="230" fill="url(#cFloor)" />
          <polygon points="430,0 770,0 980,560 220,560" fill="url(#cLight)" />
          {/* door for the bailiff */}
          <rect x="30" y="170" width="90" height="160" rx="4" fill="#24170c" stroke="#e7b75f" strokeOpacity=".25" />
          {/* raised bench */}
          <rect x="400" y="230" width="400" height="100" rx="8" fill="url(#cWood)" stroke="#e7b75f" strokeOpacity=".45" />
          <rect x="400" y="230" width="400" height="10" rx="4" fill="#e7b75f" opacity=".55" />
          {/* witness box with the investor */}
          <rect x="845" y="257" width="120" height="58" rx="6" fill="url(#cWood)" stroke="#e7b75f" strokeOpacity=".3" />
          <g transform={`translate(${INVESTOR.x + 5} ${INVESTOR.y + 4})`} opacity=".9"><Person robe="#3b4252" trim="#9aa4b8" /></g>
          <text x={INVESTOR.x + 5} y="335" textAnchor="middle" fontSize="12" fill="#8b95ad">Investor</text>
          {/* the court members */}
          {(Object.keys(CAST) as (keyof typeof CAST)[]).map((key) => {
            const c = CAST[key];
            const on = seatOn(key);
            const speaking = !running && speaker === key && typed < full;
            return (
              <g key={key} data-testid={`seat-${key}`} data-active={on ? "true" : "false"}
                className={`seat${on ? " seat-active" : ""}${speaking ? " speaking" : ""}`} transform={`translate(${c.x} ${c.y})`}>
                {on && <ellipse cx="0" cy="-40" rx="95" ry="80" fill="url(#cGlow)" />}
                <Person robe={c.robe} trim={c.trim} judge={key === "judge"} />
                {key !== "judge" && <rect x="-52" y="-6" width="104" height="40" rx="5" fill="url(#cWood)" stroke={c.trim} strokeOpacity={on ? .9 : .3} />}
                <text x="0" y={key === "judge" ? 78 : 52} textAnchor="middle" fontSize="15" fontWeight="700" fill={on ? c.trim : "#e9edf6"}>
                  {c.icon} {SPEAKER_NAME[key]}
                </text>
                <text x="0" y={key === "judge" ? 96 : 68} textAnchor="middle" fontSize="11" fill="#8b95ad">{c.role}</text>
              </g>
            );
          })}
          {/* gavel */}
          <g className={`gavel${gavel ? " strike" : ""}`} transform="translate(700 222)">
            <rect x="-4" y="-34" width="8" height="34" rx="3" fill="#8a5a2b" transform="rotate(-35)" />
            <rect x="-22" y="-46" width="30" height="16" rx="4" fill="#a8743f" transform="rotate(-35)" />
          </g>
          {/* gallery */}
          {Array.from({ length: 14 }, (_, i) => (
            <circle key={i} cx={60 + i * 82} cy="548" r="22" fill="#000" opacity=".55" />
          ))}
        </svg>
        {current && pos && (
          <div className={`speech-bubble speaker-${current.speaker}`} style={{ left: `${bubbleLeft}%`, top: `${bubbleTop}%` }}
            data-testid="speech-bubble" aria-live="polite">
            <strong>{SPEAKER_NAME[current.speaker]}</strong>
            {current.struck && <p className="struck">{current.struck}</p>}
            <p>{current.text.slice(0, typed)}<span className="caret" aria-hidden="true">{typed < full ? "▍" : ""}</span></p>
          </div>
        )}
      </div>
      <div className="court-controls">
        <span className="court-caption"><span className="dot" style={{ color: running ? "#e7b75f" : "#34d399" }} />
          {!running && !finished && playing ? "The hearing is replayed from the court record…" : caption}</span>
        <span className="court-buttons">
          <button type="button" disabled={running || index === 0} onClick={() => { setIndex((i) => Math.max(0, i - 1)); setTyped(0); }} aria-label="Previous speech">◀</button>
          <button type="button" disabled={running || !speeches.length} data-testid="replay"
            onClick={() => { if (finished) { setIndex(0); setTyped(0); setPlaying(true); } else setPlaying((p) => !p); }}>
            {finished ? "↻ Replay the hearing" : playing ? "❚❚ Pause" : "▶ Play"}
          </button>
          <button type="button" disabled={running || index >= speeches.length - 1} onClick={() => { setIndex((i) => i + 1); setTyped(0); }} aria-label="Next speech">▶</button>
          <button type="button" disabled={running} onClick={() => { setIndex(Math.max(0, speeches.findIndex((s) => s.speaker === "judge"))); setTyped(0); setPlaying(false); }}>Skip to verdict</button>
          {speak && <button type="button" aria-pressed={voice} onClick={() => setVoice((v) => !v)}>{voice ? "🔊 Voices on" : "🔈 Voices off"}</button>}
        </span>
      </div>
      {speeches.length > 0 && (
        <ol className="court-record" aria-label="Court record" data-testid="court-record">
          {speeches.slice(0, index + 1).map((s, i) => (
            <li key={s.id} className={`record-${s.speaker}${i === index ? " current" : ""}`}>
              <button type="button" className="record-speaker" onClick={() => { setIndex(i); setTyped(0); setPlaying(false); }}>{SPEAKER_NAME[s.speaker]}</button>
              <span>
                {s.struck && <del>{s.struck} </del>}
                {s.text}{" "}
                {s.exhibits.map((n) => <ExhibitLink key={n} number={n} onOpen={onOpen} />)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
