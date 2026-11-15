import type { Answer, SessionView } from "../model/sessionView";
import { ExhibitLink } from "./ExhibitLinks";

export const MAX_WORDS = 60;

/** Joins statements and cuts the text to at most `max` words (Req. 33.4). */
export function limitWords(texts: string[], max: number = MAX_WORDS): string {
  const words = texts.join(" ").split(/\s+/).filter(Boolean);
  if (words.length <= max) return words.join(" ");
  return words.slice(0, max - 1).join(" ") + "…";
}

/** The four headed answers of the Ruling, each short, with Exhibit links (Req. 33.1, 33.4). */
export function FourAnswersCard({
  answers, onOpen,
}: { answers: Answer[]; onOpen: (n: number) => void }) {
  if (answers.length === 0) return null;
  return (
    <section aria-label="Four answers" data-testid="four-answers">
      {answers.map((a) => {
        const numbers = [...new Set(a.statements.flatMap((s) => s.citations))].sort((x, y) => x - y);
        return (
          <article key={a.id} data-testid={`answer-${a.id}`}>
            <h3>{a.heading}</h3>
            <p data-testid={`answer-text-${a.id}`}>{limitWords(a.statements.map((s) => s.text))}</p>
            {numbers.map((n) => (
              <ExhibitLink key={n} number={n} onOpen={(x) => onOpen(x)} />
            ))}
          </article>
        );
      })}
    </section>
  );
}

export function answersOf(view: SessionView): Answer[] {
  return view.ruling?.questions ?? [];
}
