import { useEffect, useState } from "react";
import type { Focus, SessionView } from "../model/sessionView";
import { ExhibitCard } from "../advanced/ExhibitCard";
import { Courtroom } from "./Courtroom";
import { SPEAKER_NAME, hearingOf } from "./hearing";
import type { Weights } from "../Portfolio";
import { CourtroomTimeline } from "./CourtroomTimeline";
import { LiveProgress } from "./LiveProgress";
import { FourAnswersCard, answersOf } from "./FourAnswersCard";
import { NewsCards, newsOf } from "./NewsCards";
import { VerdictPanel } from "./VerdictPanel";
import { TribunalArguments } from "./Arguments";


/** The investor's view: real progress and arguments while the hearing runs, then the decision.
 * The courtroom is one click away ("Follow the hearing"); it reads the same session, never a second run. */
export function FriendlyMode({
  view, onSeeDetails, inlineExhibits = false, portfolio,
}: {
  view: SessionView; onSeeDetails: (focus: Focus) => void;
  /** Current holdings of the investor, for the before-and-after comparison on the verdict. */
  portfolio?: Weights | null;
  /** Open Exhibits in a side panel, so the reader keeps their place in the hearing. */
  inlineExhibits?: boolean;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const [follow, setFollow] = useState(false);
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
  const running = view.status === "running";
  const speeches = hearingOf(view).filter((x) => x.speaker !== "bailiff" && x.speaker !== "clerk");
  const answers = answersOf(view);
  const news = newsOf(view);
  return (
    <div data-testid="friendly-mode">
      <LiveProgress key={view.session_id} view={view} />
      {running && speeches.length > 0 && !follow && (
        <section className="card live-args" aria-label="Arguments so far" data-testid="live-arguments">
          <h3>Arguments so far</h3>
          <ol>
            {speeches.map((x) => <li key={x.id} className={`arg-${x.speaker}`}><b>{SPEAKER_NAME[x.speaker]}</b> {x.text}</li>)}
          </ol>
        </section>
      )}
      <VerdictPanel view={view} onSeeDetails={see} portfolio={portfolio} />
      <div className="follow-bar">
        <button type="button" aria-expanded={follow} onClick={() => setFollow((f) => !f)} data-testid="follow-toggle">
          {follow ? "Hide the hearing" : running ? "Follow the hearing" : "Replay the hearing"}
        </button>
      </div>
      {follow && <Courtroom view={view} onOpen={openExhibit} />}
      {view.status === "completed" && (
        <details className="card more reasoning" data-testid="view-arguments">
          <summary><h2>View the arguments</h2></summary>
          <TribunalArguments view={view} onOpen={openExhibit} />
        </details>
      )}
      {view.status === "completed" && (
        <details className="card more reasoning" data-testid="reasoning">
          <summary><h2>Understand the reasoning</h2></summary>
          <CourtroomTimeline view={view} onOpen={openExhibit} />
          <FourAnswersCard answers={answers} onOpen={openExhibit} />
          <NewsCards items={news} onOpen={openExhibit} />
        </details>
      )}
      {shown && (
        <div className="drawer-backdrop" onClick={() => setOpen(null)}>
          <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Evidence ${shown.number}`} onClick={(e) => e.stopPropagation()}>
            <div className="drawer-head">
              <span>Evidence</span>
              <button type="button" onClick={() => setOpen(null)} aria-label="Close evidence">Close</button>
            </div>
            <ExhibitCard exhibit={shown} />
            <button type="button" className="drawer-all" onClick={() => { setOpen(null); onSeeDetails({ kind: "exhibit", number: shown.number }); }}>
              See all evidence in the detailed analysis
            </button>
          </aside>
        </div>
      )}
    </div>
  );
}
