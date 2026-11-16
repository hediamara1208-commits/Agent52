import type { ReactNode } from "react";

/** The court's cast: stylized cartoon characters, drawn in SVG (no photos, no real faces).
 * Each is drawn around (0,0) = the point where the body meets the desk; about 150 tall. */
export type Cast = "judge" | "advocate" | "investigator" | "clerk" | "bailiff" | "investor";
export type Mood = "idle" | "speaking" | "listening" | "stern";

const INK = "#1c1626";

function Eyes({ y, gap = 11, mood, glasses = false }: { y: number; gap?: number; mood: Mood; glasses?: boolean }) {
  return (
    <g className="eyes">
      {[-gap, gap].map((x) => (
        <g key={x}>
          {glasses && <circle cx={x} cy={y} r="8.5" fill="#ffffff22" stroke={INK} strokeWidth="2" />}
          <ellipse className="eye" cx={x} cy={y} rx="3.4" ry="4.4" fill={INK} />
          <circle cx={x + 1.2} cy={y - 1.5} r="1.1" fill="#fff" />
          <path className="brow" d={mood === "stern"
            ? (x < 0 ? `M ${x - 6} ${y - 12} L ${x + 6} ${y - 8}` : `M ${x - 6} ${y - 8} L ${x + 6} ${y - 12}`)
            : `M ${x - 6} ${y - 10} Q ${x} ${y - 13} ${x + 6} ${y - 10}`}
            stroke={INK} strokeWidth="2.2" strokeLinecap="round" fill="none" />
        </g>
      ))}
      {glasses && <path d={`M ${-gap + 8.5} ${y} L ${gap - 8.5} ${y}`} stroke={INK} strokeWidth="2" />}
    </g>
  );
}

function Mouth({ y, mood }: { y: number; mood: Mood }) {
  if (mood === "speaking") return <ellipse className="mouth-talk" cx="0" cy={y} rx="5" ry="3.5" fill="#7a2f3a" />;
  if (mood === "stern") return <path d={`M -5 ${y + 1} L 5 ${y + 1}`} stroke={INK} strokeWidth="2.2" strokeLinecap="round" />;
  return <path d={`M -6 ${y - 1} Q 0 ${y + 4} 6 ${y - 1}`} stroke={INK} strokeWidth="2.2" strokeLinecap="round" fill="none" />;
}

function Head({ skin, y = -92, children }: { skin: string; y?: number; children?: ReactNode }) {
  return (
    <g className="head">
      <rect x="-7" y={y + 22} width="14" height="14" rx="5" fill={skin} />
      <ellipse cx="0" cy={y} rx="25" ry="27" fill={skin} stroke={INK} strokeWidth="2" />
      {children}
    </g>
  );
}

function Judge({ mood }: { mood: Mood }) {
  return (
    <g>
      <path d="M -52 0 Q -54 -58 -22 -64 L 22 -64 Q 54 -58 52 0 Z" fill="#1d1a2b" stroke={INK} strokeWidth="2" />
      <path d="M -14 -64 L 0 -40 L 14 -64 Z" fill="#f4f1ea" />
      <path d="M -22 -64 Q 0 -50 22 -64" fill="none" stroke="#e7b75f" strokeWidth="4" />
      <Head skin="#f0cfae">
        {/* wig: rows of curls */}
        <path d="M -30 -84 Q -36 -122 0 -124 Q 36 -122 30 -84 Q 34 -66 26 -60 L 22 -84 Q 0 -100 -22 -84 L -26 -60 Q -34 -66 -30 -84 Z" fill="#f7f4ec" stroke={INK} strokeWidth="2" />
        {[-24, -12, 0, 12, 24].map((x) => <circle key={x} cx={x} cy={-112 + Math.abs(x) / 4} r="6" fill="none" stroke="#cfc8b8" strokeWidth="1.6" />)}
        <Eyes y={-94} mood={mood} glasses />
        <Mouth y={-78} mood={mood} />
      </Head>
    </g>
  );
}

function Advocate({ mood }: { mood: Mood }) {
  return (
    <g>
      <path d="M -46 0 Q -48 -52 -20 -62 L 20 -62 Q 48 -52 46 0 Z" fill="#12607a" stroke={INK} strokeWidth="2" />
      <path d="M -12 -62 L 0 -34 L 12 -62 Z" fill="#fff" />
      <path d="M -3 -52 L 3 -52 L 5 -30 L 0 -24 L -5 -30 Z" fill="#e7b75f" />
      {/* raised hand while pleading */}
      <g className="arm">
        <path d="M 40 -34 Q 62 -50 60 -74" fill="none" stroke="#12607a" strokeWidth="12" strokeLinecap="round" />
        <circle cx="60" cy="-78" r="8" fill="#c98d62" stroke={INK} strokeWidth="2" />
      </g>
      <Head skin="#c98d62">
        <path d="M -27 -98 Q -30 -126 2 -124 Q 32 -122 27 -94 Q 18 -112 -4 -108 Q -18 -106 -27 -98 Z" fill="#2b1a12" stroke={INK} strokeWidth="2" />
        <Eyes y={-92} mood={mood} />
        <Mouth y={-77} mood={mood} />
      </Head>
    </g>
  );
}

function Investigator({ mood }: { mood: Mood }) {
  return (
    <g>
      <path d="M -46 0 Q -50 -54 -20 -62 L 20 -62 Q 50 -54 46 0 Z" fill="#7a3a28" stroke={INK} strokeWidth="2" />
      <path d="M -20 -62 L -4 -30 L 0 -44 L 4 -30 L 20 -62" fill="#5a2a1e" stroke={INK} strokeWidth="2" />
      {/* magnifying glass */}
      <g className="arm">
        <path d="M -40 -30 Q -60 -44 -58 -62" fill="none" stroke="#7a3a28" strokeWidth="12" strokeLinecap="round" />
        <circle cx="-60" cy="-78" r="13" fill="#bfe9ff55" stroke="#e7b75f" strokeWidth="4" />
        <path d="M -52 -68 L -46 -58" stroke="#8a5a2b" strokeWidth="5" strokeLinecap="round" />
      </g>
      <Head skin="#f3d2b8">
        <path d="M -28 -92 Q -30 -124 0 -124 Q 30 -124 28 -92 L 22 -104 Q 0 -112 -22 -104 Z" fill="#b5532a" stroke={INK} strokeWidth="2" />
        <circle cx="0" cy="-126" r="9" fill="#b5532a" stroke={INK} strokeWidth="2" />
        <Eyes y={-92} mood={mood} glasses />
        <Mouth y={-76} mood={mood} />
      </Head>
    </g>
  );
}

function Clerk({ mood }: { mood: Mood }) {
  return (
    <g>
      <path d="M -42 0 Q -44 -50 -18 -60 L 18 -60 Q 44 -50 42 0 Z" fill="#1c6b54" stroke={INK} strokeWidth="2" />
      <path d="M -12 -60 L 0 -36 L 12 -60 Z" fill="#fff" />
      <circle cx="0" cy="-30" r="3" fill="#e7b75f" /><circle cx="0" cy="-18" r="3" fill="#e7b75f" />
      {/* quill */}
      <g className="arm">
        <path d="M 30 -8 Q 40 -40 62 -62" stroke="#f4f1ea" strokeWidth="5" strokeLinecap="round" fill="none" />
        <path d="M 44 -44 Q 66 -72 62 -62 Q 60 -48 44 -44 Z" fill="#f4f1ea" stroke={INK} strokeWidth="1.5" />
      </g>
      <Head skin="#8d5a3c" y={-88}>
        <path d="M -27 -90 Q -30 -120 0 -118 Q 30 -120 27 -90 Q 14 -106 -27 -90 Z" fill="#15100e" stroke={INK} strokeWidth="2" />
        <Eyes y={-88} mood={mood} />
        <Mouth y={-73} mood={mood} />
      </Head>
    </g>
  );
}

/** The Bailiff is the code, so it is a small robot: it never has an opinion, it checks. */
function Bailiff({ mood }: { mood: Mood }) {
  return (
    <g>
      <rect x="-36" y="-58" width="72" height="58" rx="14" fill="#b98a3e" stroke={INK} strokeWidth="2" />
      <rect x="-20" y="-46" width="40" height="22" rx="6" fill="#231a0c" />
      <path className="scan" d="M -14 -35 L 14 -35" stroke="#7df0b4" strokeWidth="3" strokeLinecap="round" />
      <rect x="-6" y="-66" width="12" height="10" fill="#8a6427" />
      <g className="head">
        <rect x="-28" y="-116" width="56" height="50" rx="14" fill="#d6a756" stroke={INK} strokeWidth="2" />
        <path d="M 0 -116 L 0 -130" stroke={INK} strokeWidth="2.5" /><circle className="antenna" cx="0" cy="-133" r="5" fill="#7df0b4" stroke={INK} strokeWidth="2" />
        <rect x="-20" y="-104" width="40" height="20" rx="8" fill="#231a0c" />
        <circle className="eye" cx="-9" cy="-94" r="4.5" fill="#7df0b4" /><circle className="eye" cx="9" cy="-94" r="4.5" fill="#7df0b4" />
        {mood === "speaking"
          ? <rect className="mouth-talk" x="-9" y="-79" width="18" height="6" rx="3" fill="#231a0c" />
          : <path d="M -8 -76 L 8 -76" stroke="#231a0c" strokeWidth="3" strokeLinecap="round" />}
      </g>
    </g>
  );
}

function Investor({ mood }: { mood: Mood }) {
  return (
    <g>
      <path d="M -40 0 Q -42 -48 -18 -58 L 18 -58 Q 42 -48 40 0 Z" fill="#5b6478" stroke={INK} strokeWidth="2" />
      <path d="M -10 -58 Q 0 -44 10 -58" fill="#e9edf6" />
      <Head skin="#e8c39e" y={-86}>
        <path d="M -26 -92 Q -26 -116 0 -116 Q 26 -116 26 -92 Q 10 -104 -26 -92 Z" fill="#8f8f95" stroke={INK} strokeWidth="2" />
        <Eyes y={-86} mood={mood} />
        <Mouth y={-71} mood={mood} />
      </Head>
    </g>
  );
}

const DRAW: Record<Cast, (p: { mood: Mood }) => ReactNode> = {
  judge: Judge, advocate: Advocate, investigator: Investigator, clerk: Clerk, bailiff: Bailiff, investor: Investor,
};

export function Character({ who, mood = "idle" }: { who: Cast; mood?: Mood }) {
  const Draw = DRAW[who];
  return <g className={`character character-${who} mood-${mood}`} data-mood={mood}>{Draw({ mood })}</g>;
}
