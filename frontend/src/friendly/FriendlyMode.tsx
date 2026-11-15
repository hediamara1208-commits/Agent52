import type { Focus, SessionView } from "../model/sessionView";
import { Courtroom } from "./Courtroom";
import type { Speech } from "./hearing";
import { CourtroomTimeline } from "./CourtroomTimeline";
import { LiveProgress } from "./LiveProgress";
import { FourAnswersCard, answersOf } from "./FourAnswersCard";
import { NewsCards, newsOf } from "./NewsCards";
import { VerdictPanel } from "./VerdictPanel";


/** Friendly_Mode: animated courtroom, short statements, verdict reveal (Req. 7.10 to 7.12, 7.17). */
export function FriendlyMode({
  view, onSeeDetails, speak,
}: { view: SessionView; onSeeDetails: (focus: Focus) => void; speak?: (speech: Speech) => Promise<void> }) {
  return (
    <div data-testid="friendly-mode">
      <Courtroom view={view} onOpen={(number) => onSeeDetails({ kind: "exhibit", number })} speak={speak} />
      <LiveProgress key={view.session_id} view={view} />
      <VerdictPanel view={view} onSeeDetails={onSeeDetails} />
      <CourtroomTimeline view={view} onOpen={(number) => onSeeDetails({ kind: "exhibit", number })} />
      <FourAnswersCard
        answers={answersOf(view)}
        onOpen={(number) => onSeeDetails({ kind: "exhibit", number })}
      />
      <NewsCards items={newsOf(view)} onOpen={(number) => onSeeDetails({ kind: "exhibit", number })} />
    </div>
  );
}
