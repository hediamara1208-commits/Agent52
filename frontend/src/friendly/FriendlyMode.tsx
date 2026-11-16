import { useEffect, useState } from "react";
import type { Focus, SessionView } from "../model/sessionView";
import { ExhibitCard } from "../advanced/ExhibitCard";
import { Courtroom } from "./Courtroom";
import type { Speech } from "./hearing";
import { CourtroomTimeline } from "./CourtroomTimeline";
import { LiveProgress } from "./LiveProgress";
import { FourAnswersCard, answersOf } from "./FourAnswersCard";
import { NewsCards, newsOf } from "./NewsCards";
import { VerdictPanel } from "./VerdictPanel";


/** Friendly_Mode: animated courtroom, short statements, verdict reveal (Req. 7.10 to 7.12, 7.17). */
export function FriendlyMode({
  view, onSeeDetails, speak, inlineExhibits = false,
}: {
  view: SessionView; onSeeDetails: (focus: Focus) => void; speak?: (speech: Speech) => Promise<void>;
  /** Open Exhibits in a side panel, so the reader keeps their place in the hearing. */
  inlineExhibits?: boolean;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const see = (focus: Focus) => {
    if (inlineExhibits && focus.kind === "exhibit" && view.exhibits.some((e) => e.number === focus.number)) setOpen(focus.number);
    else onSeeDetails(focus);
  };
  const openExhibit = (number: number) => see({ kind: "exhibit", number });
  useEffect(() => {
    if (open === null) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
  const shown = open === null ? undefined : view.exhibits.find((e) => e.number === open);
  return (
    <div data-testid="friendly-mode">
      <Courtroom view={view} onOpen={openExhibit} speak={speak} />
      <LiveProgress key={view.session_id} view={view} />
      <VerdictPanel view={view} onSeeDetails={see} />
      <CourtroomTimeline view={view} onOpen={openExhibit} />
      <FourAnswersCard answers={answersOf(view)} onOpen={openExhibit} />
      <NewsCards items={newsOf(view)} onOpen={openExhibit} />
      {shown && (
        <div className="drawer-backdrop" onClick={() => setOpen(null)}>
          <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Exhibit ${shown.number}`} onClick={(e) => e.stopPropagation()}>
            <div className="drawer-head">
              <span>Evidence</span>
              <button type="button" onClick={() => setOpen(null)} aria-label="Close evidence">✕ Close</button>
            </div>
            <ExhibitCard exhibit={shown} />
            <button type="button" className="drawer-all" onClick={() => { setOpen(null); onSeeDetails({ kind: "exhibit", number: shown.number }); }}>
              See all evidence in Advanced mode
            </button>
          </aside>
        </div>
      )}
    </div>
  );
}
