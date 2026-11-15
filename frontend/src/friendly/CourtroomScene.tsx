import type { SessionView } from "../model/sessionView";

export const SEATS = [
  { agent: "investigator", label: "Investigator", role: "Names the risks", x: 120, y: 214, color: "#8b7bff", icon: "🔎" },
  { agent: "advocate", label: "Advocate", role: "Proposes options", x: 300, y: 214, color: "#4fd1e8", icon: "⚖" },
  { agent: "judge", label: "Judge", role: "Weighs preferences", x: 600, y: 120, color: "#e7b75f", icon: "🏛" },
  { agent: "clerk", label: "Clerk", role: "Writes the ruling", x: 900, y: 214, color: "#34d399", icon: "📜" },
] as const;

const CAPTION: Record<string, string> = {
  advocate: "The Advocate is building options that serve your goal…",
  investigator: "The Investigator is naming the risks that matter for you…",
  judge: "The Judge is weighing your preferences against the rules…",
  clerk: "The Clerk is writing the ruling…",
};

function Figure({ color, icon }: { color: string; icon: string }) {
  return (
    <g className="figure">
      <circle cx="0" cy="-58" r="20" fill={color} opacity="0.95" />
      <path d="M -30 -10 Q -30 -36 0 -36 Q 30 -36 30 -10 Z" fill={color} opacity="0.75" />
      <text x="0" y="-51" textAnchor="middle" fontSize="18">{icon}</text>
    </g>
  );
}

/** Animated tribunal: the active agent glows and speaks (Req. 7.10). Seat test ids are stable. */
export function CourtroomScene({ activeAgent }: { activeAgent: SessionView["active_agent"] }) {
  const active = activeAgent?.toLowerCase() ?? null;
  return (
    <div className="card courtroom">
      <svg role="img" aria-label="Courtroom scene" viewBox="0 0 1200 320" width="100%">
        <defs>
          <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#1a2340" />
            <stop offset="1" stopColor="#070b16" />
          </linearGradient>
          <linearGradient id="wood" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#3b2a17" />
            <stop offset="1" stopColor="#1d140b" />
          </linearGradient>
          <radialGradient id="spot" cx="0.5" cy="0" r="0.8">
            <stop offset="0" stopColor="#f6d58e" stopOpacity="0.28" />
            <stop offset="1" stopColor="#f6d58e" stopOpacity="0" />
          </radialGradient>
          {SEATS.map((s) => (
            <radialGradient key={s.agent} id={`glow-${s.agent}`} cx="0.5" cy="0.5" r="0.5">
              <stop offset="0" stopColor={s.color} stopOpacity="0.55" />
              <stop offset="1" stopColor={s.color} stopOpacity="0" />
            </radialGradient>
          ))}
        </defs>
        <rect width="1200" height="320" fill="url(#floor)" />
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <rect key={i} x={100 + i * 180} y="0" width="18" height="250" fill="#ffffff" opacity="0.025" />
        ))}
        <polygon points="470,0 730,0 860,320 340,320" fill="url(#spot)" />
        <rect x="430" y="150" width="340" height="80" rx="10" fill="url(#wood)" stroke="#e7b75f" strokeOpacity="0.35" />
        <rect x="430" y="150" width="340" height="8" rx="4" fill="#e7b75f" opacity="0.5" />
        <text x="600" y="200" textAnchor="middle" fontSize="15" fill="#f6d58e" letterSpacing="6" opacity="0.8">
          THE TRIBUNAL
        </text>
        <rect x="0" y="250" width="1200" height="70" fill="#000" opacity="0.25" />
        {SEATS.map((s) => {
          const on = s.agent === active;
          return (
            <g
              key={s.agent}
              data-testid={`seat-${s.agent}`}
              data-active={on ? "true" : "false"}
              className={on ? "seat seat-active" : "seat"}
              transform={`translate(${s.x} ${s.y})`}
              opacity={active && !on ? 0.5 : 1}
            >
              <ellipse className="seat-glow" cx="0" cy="-40" rx="110" ry="90" fill={`url(#glow-${s.agent})`} />
              <circle className="speaking-ring" cx="0" cy="-58" r="26" fill="none" stroke={s.color} strokeWidth="2" />
              <Figure color={s.color} icon={s.icon} />
              {s.agent !== "judge" && <rect x="-55" y="-10" width="110" height="34" rx="6" fill="url(#wood)" stroke={s.color} strokeOpacity={on ? 0.9 : 0.3} />}
              <text x="0" y={s.agent === "judge" ? 120 : 52} textAnchor="middle" fontSize="16" fontWeight="700" fill={on ? s.color : "#e9edf6"}>
                {s.label}
              </text>
              <text x="0" y={s.agent === "judge" ? 140 : 72} textAnchor="middle" fontSize="12" fill="#8b95ad">
                {s.role}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="court-caption">
        <span className="dot" style={{ color: active ? "#e7b75f" : "#34d399" }} />
        {active ? CAPTION[active] ?? "The tribunal is in session…" : "The tribunal has risen."}
      </p>
    </div>
  );
}
