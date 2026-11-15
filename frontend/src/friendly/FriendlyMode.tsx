import type { Focus, SessionView } from "../model/sessionView";
import { CourtroomScene } from "./CourtroomScene";
import { FourAnswersCard, answersOf } from "./FourAnswersCard";
import { VerdictPanel } from "./VerdictPanel";

/** Friendly_Mode: courtroom, short summaries, verdict (Req. 7.10 to 7.12, 7.17). */
export function FriendlyMode({
  view, onSeeDetails,
}: { view: SessionView; onSeeDetails: (focus: Focus) => void }) {
  const entries = Object.entries(view.summaries);
  return (
    <div data-testid="friendly-mode">
      <CourtroomScene activeAgent={view.active_agent} />
      <section aria-label="Summaries">
        {entries.map(([key, text]) => (
          <p key={key} data-testid={`summary-${key}`}>
            <strong>{key}:</strong> {text}
          </p>
        ))}
      </section>
      <VerdictPanel view={view} onSeeDetails={onSeeDetails} />
      <FourAnswersCard
        answers={answersOf(view)}
        onOpen={(number) => onSeeDetails({ kind: "exhibit", number })}
      />
    </div>
  );
}
