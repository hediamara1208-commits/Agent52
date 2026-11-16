import { useId, useMemo, useRef, useState } from "react";
import { KIND_LABEL, UNIVERSE, searchSecurities, type Security } from "./universe";

/**
 * Searchable selector over the securities the toolkit has validated price history for.
 * Keyboard: arrows move, Enter picks, Escape closes. A query with no match explains why
 * nothing is offered rather than accepting an asset that cannot be analysed.
 */
export function SecuritySearch({ value, onPick, autoFocus = false }: {
  value: Security | null; onPick: (s: Security | null) => void; autoFocus?: boolean;
}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const results = useMemo(() => searchSecurities(query), [query]);
  const pick = (s: Security) => { onPick(s); setQuery(""); setOpen(false); };
  const clear = () => { onPick(null); setQuery(""); setOpen(true); setTimeout(() => input.current?.focus(), 0); };

  if (value) {
    return (
      <div className="sec-picked" data-testid="security-picked">
        <div>
          <b>{value.name}</b>
          <span className="sec-meta">{value.ticker} · {value.exchange} · {value.currency} · {KIND_LABEL[value.kind]}</span>
        </div>
        <button type="button" className="btn-quiet" onClick={clear} aria-label={`Change security, currently ${value.name}`}>Change</button>
      </div>
    );
  }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && open && results[active]) { e.preventDefault(); pick(results[active]); }
    else if (e.key === "Escape") setOpen(false);
  };
  return (
    <div className="sec-search">
      <input ref={input} id={id} type="text" role="combobox" aria-label="Stock or ETF" aria-expanded={open} aria-controls={`${id}-list`}
        aria-autocomplete="list" aria-activedescendant={open && results[active] ? `${id}-opt-${active}` : undefined}
        autoComplete="off" spellCheck={false} autoFocus={autoFocus} placeholder="Search by name or ticker, e.g. Tesla"
        value={query} onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)} onKeyDown={onKey} />
      {open && (
        results.length > 0 ? (
          <ul id={`${id}-list`} role="listbox" aria-label="Securities" className="sec-list">
            {results.map((s, i) => (
              <li key={s.ticker} id={`${id}-opt-${i}`} role="option" aria-selected={i === active} className={i === active ? "on" : ""}
                onMouseDown={(e) => { e.preventDefault(); pick(s); }} onMouseEnter={() => setActive(i)}>
                <span className="sec-name">{s.name}</span>
                <span className="sec-ticker">{s.ticker}</span>
                <span className="sec-meta">{s.exchange} · {s.currency} · {KIND_LABEL[s.kind]}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p id={`${id}-list`} role="status" className="sec-none" data-testid="security-none">
            “{query.trim()}” is not among the {UNIVERSE.length} securities VERDICT can analyse. A ruling needs validated price
            history, so nothing is offered for securities outside that dataset, including private companies and indices.
          </p>
        )
      )}
    </div>
  );
}

/** "30" → 30; rejects empty, non-numeric, zero, negative and above 100. */
export function parseAllocation(text: string): { ok: true; value: number } | { ok: false; error: string | null } {
  const t = text.trim().replace(",", ".");
  if (t === "") return { ok: false, error: null };
  const n = Number(t);
  if (!Number.isFinite(n)) return { ok: false, error: "Enter a number, for example 30." };
  if (n <= 0) return { ok: false, error: "The allocation must be above 0%." };
  if (n > 100) return { ok: false, error: "The allocation cannot exceed 100% of the portfolio." };
  return { ok: true, value: n };
}
