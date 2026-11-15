import type { Focus, SessionView } from "../model/sessionView";
import { ExhibitList } from "./ExhibitList";
import { RuleTable } from "./RuleTable";
import { SensitivityPanel } from "./SensitivityPanel";
import { TracePanel } from "./TracePanel";

/** Advanced_Mode: Exhibits, rules, sensitivity, trace over the shared SessionView (Req. 7.6, 7.7, 7.17). */
export function AdvancedMode({ view, focus, onFocus }: {
  view: SessionView; focus: Focus | null; onFocus: (focus: Focus) => void;
}) {
  const openExhibit = (number: number) => onFocus({ kind: "exhibit", number });
  return (
    <div data-testid="advanced-mode">
      <ExhibitList exhibits={view.exhibits} focusedNumber={focus?.kind === "exhibit" ? focus.number : null} onFocus={openExhibit} />
      <RuleTable rules={view.rule_results} focusedRule={focus?.kind === "rule" ? focus.rule : null} onExhibit={openExhibit} />
      <SensitivityPanel results={view.sensitivity} onExhibit={openExhibit} />
      <TracePanel trace={view.trace} focusedSeq={focus?.kind === "trace" ? focus.seq : null} onExhibit={openExhibit} />
    </div>
  );
}
