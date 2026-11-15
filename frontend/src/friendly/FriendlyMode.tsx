import type { Focus, SessionView } from "../model/sessionView";
import { CourtroomScene } from "./CourtroomScene";
import { FourAnswersCard, answersOf } from "./FourAnswersCard";
import { NewsCards, newsOf } from "./NewsCards";
import { VerdictPanel } from "./VerdictPanel";

const AGENT_TITLE: Record<string, string> = { advocate: "Advocate", investigator: "Investigator", judge: "Judge" };
const AGENT_ICON: Record<string, string> = { advocate: "⚖", investigator: "🔎", judge: "🏛" };

/** Friendly_Mode: animated courtroom, short statements, verdict reveal (Req. 7.10 to 7.12, 7.17). */
export function FriendlyMode({
  view, onSeeDetails,
}: { view: SessionView; onSeeDetails: (focus: Focus) => void }) {
  const entries = Object.entries(view.summaries);
  return (
    <div data-testid="friendly-mode">
      <CourtroomScene activeAgent={view.active_agent} />
      {entries.length > 0 && (
        <section aria-label="Summaries" className="statements">
          {entries.map(([key, text]) => (
            <p key={key} data-testid={`summary-${key}`} data-agent={key} className="bubble">
              <strong><span aria-hidden="true">{AGENT_ICON[key] ?? "•"}</span>{AGENT_TITLE[key] ?? key}</strong> {text}
            </p>
          ))}
        </section>
      )}
      <VerdictPanel view={view} onSeeDetails={onSeeDetails} />
      <FourAnswersCard
        answers={answersOf(view)}
        onOpen={(number) => onSeeDetails({ kind: "exhibit", number })}
      />
      <NewsCards items={newsOf(view)} onOpen={(number) => onSeeDetails({ kind: "exhibit", number })} />
    </div>
  );
}
