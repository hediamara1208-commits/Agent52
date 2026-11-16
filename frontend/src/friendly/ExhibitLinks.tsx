import type { Statement } from "../model/sessionView";
import { plain } from "./plain";

/** `[Exhibit N]` link that sets focus and opens Advanced_Mode. */
export function ExhibitLink({ number, onOpen }: { number: number; onOpen: (n: number) => void }) {
  return (
    <button type="button" className="exhibit-link" onClick={() => onOpen(number)}>
      Evidence {number}
    </button>
  );
}

export function StatementText({ statement, onOpen }: { statement: Statement; onOpen: (n: number) => void }) {
  return (
    <span data-testid="statement">
      {plain(statement.text)}{" "}
      {statement.citations.map((n) => (
        <ExhibitLink key={n} number={n} onOpen={onOpen} />
      ))}
    </span>
  );
}
