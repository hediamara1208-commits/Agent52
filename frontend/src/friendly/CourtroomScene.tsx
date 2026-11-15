import type { SessionView } from "../model/sessionView";

export const SEATS = [
  { agent: "investigator", label: "Investigator", x: 20 },
  { agent: "advocate", label: "Advocate", x: 170 },
  { agent: "judge", label: "Judge", x: 320 },
  { agent: "clerk", label: "Clerk", x: 470 },
] as const;

/** Inline SVG courtroom with four seats; the seat of `activeAgent` is highlighted (Req. 7.10). */
export function CourtroomScene({ activeAgent }: { activeAgent: SessionView["active_agent"] }) {
  const active = activeAgent?.toLowerCase() ?? null;
  return (
    <svg role="img" aria-label="Courtroom scene" viewBox="0 0 600 160" width="100%">
      <rect x="0" y="120" width="600" height="40" fill="#e8e0d0" />
      {SEATS.map((s) => {
        const on = s.agent === active;
        return (
          <g
            key={s.agent}
            data-testid={`seat-${s.agent}`}
            data-active={on ? "true" : "false"}
            className={on ? "seat seat-active" : "seat"}
          >
            <rect
              x={s.x} y="30" width="110" height="80" rx="8"
              fill={on ? "#ffe08a" : "#f4f4f4"} stroke={on ? "#b8860b" : "#888"} strokeWidth={on ? 4 : 1}
            />
            <circle cx={s.x + 55} cy="58" r="14" fill={on ? "#b8860b" : "#aaa"} />
            <text x={s.x + 55} y="98" textAnchor="middle" fontSize="14" fontWeight={on ? "bold" : "normal"}>
              {s.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
