import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AdvancedMode } from "./advanced";
import { FriendlyMode } from "./friendly";
import { createVoice } from "./friendly/voices";
import { ApiError, type ContractValues, type CustomProfile, type PersonaEntry, type SessionApi } from "./api/client";
import type { AuthService } from "./api/auth";
import { sessionStore, useSessionStore, type SessionStore, type SessionView } from "./model/sessionView";
import { AppealControl, AppealView, type AppealChange } from "./appeal";
import { EMPTY_VALUES, FOSSIL, HoldingsField, ProfileForm, parseHoldings, valuesFromPersona } from "./ProfileForm";
import { SignInGate } from "./SignInGate";
import { SecuritySearch, parseAllocation } from "./SecuritySearch";
import type { Security } from "./universe";

export const POLL_MS = 2000;
export const MAX_WAIT_MS = 5 * 60 * 1000;
const RUNNING = "verdict.running";
const rememberSession = (id: string) => { try { sessionStorage.setItem(RUNNING, id); } catch { /* convenience only */ } };
const forgetSession = () => { try { sessionStorage.removeItem(RUNNING); } catch { /* convenience only */ } };
const runningSession = () => { try { return sessionStorage.getItem(RUNNING); } catch { return null; } };
const LAST_PROFILE = "verdict.lastProfile";
const remember = (id: string) => { try { if (id) localStorage.setItem(LAST_PROFILE, id); } catch { /* storage is a convenience only */ } };
const remembered = () => { try { return localStorage.getItem(LAST_PROFILE) ?? ""; } catch { return ""; } };
const RISK_WORD: Record<string, string> = { low: "Low risk", low_to_moderate: "Low to moderate risk", moderate: "Moderate risk", high: "High risk", very_high: "Very high risk" };
const pct = (v: number | null) => (v === null ? null : `${Number((v * 100).toFixed(1))}%`);

/** One line that tells a returning investor which constraints the tribunal will apply. */
export function profileSummary(v: ContractValues): string {
  const parts = [RISK_WORD[v.risk_level] ?? v.risk_level];
  if (v.horizon_min !== null) parts.push(v.horizon_max !== null && v.horizon_max !== v.horizon_min ? `${v.horizon_min} to ${v.horizon_max} years` : `${v.horizon_min}-year horizon`);
  if (pct(v.max_drawdown)) parts.push(`max drawdown ${pct(v.max_drawdown)}`);
  if (pct(v.max_volatility)) parts.push(`max volatility ${pct(v.max_volatility)}`);
  if (v.esg_exclusions.includes(FOSSIL)) parts.push("avoids fossil fuels");
  return parts.join(" · ");
}
export const STAGES = ["advocate", "investigator", "judge", "clerk"];

export function Banners({ view }: { view: SessionView | null }) {
  const snap = view?.snapshot;
  return (
    <header className="banners">
      <p role="note" data-testid="simulation-banner" className="pill pill-gold"><span className="dot" />Simulation only. This is not financial advice.</p>
      <p role="note" data-testid="guidance-statement" className="pill">
        This tool only provides guidance. You act personally, outside this tool.
      </p>
      {snap && (
        <p data-testid="data-badge" className="pill">
          Data: {snap.snapshot_id} · source {snap.source} · retrieved {snap.retrieved_at}
        </p>
      )}
      {snap?.served_from === "cache_fallback" && (
        <p role="alert" data-testid="fallback-notice" className="pill pill-warn">
          Served from the local cache because the primary store was unavailable
          {snap.fallback_cause ? ` (${snap.fallback_cause})` : ""}.
        </p>
      )}
    </header>
  );
}

function Progress({ view }: { view: SessionView }) {
  return (
    <ol aria-label="Stage progress" data-testid="progress" className="progress">
      {STAGES.map((s) => (
        <li key={s} data-state={view.stages_done.includes(s) ? "done" : view.stage === s && view.status === "running" ? "active" : "pending"}>
          {s}{view.stages_done.includes(s) ? " ✓" : view.stage === s && view.status === "running" ? " …" : ""}
        </li>
      ))}
    </ol>
  );
}

export function Workspace({ api, store = sessionStore, pollMs = POLL_MS }: {
  api: SessionApi; store?: SessionStore; pollMs?: number;
}) {
  const { view, mode, focus } = useSessionStore(store);
  const [personas, setPersonas] = useState<PersonaEntry[]>([]);
  const [personaError, setPersonaError] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<CustomProfile[]>([]);
  const [selected, setSelected] = useState("");
  const [values, setValues] = useState<ContractValues>(EMPTY_VALUES);
  const [requestText, setRequestText] = useState("");
  const [security, setSecurity] = useState<Security | null>(null);
  const [allocation, setAllocation] = useState("");
  const allocationInput = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [holdings, setHoldings] = useState("");
  const [appealBase, setAppealBase] = useState<{ original: SessionView; change: AppealChange } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Court voices (Amazon Polly through POST /speech), when the API offers them.
  const speak = useMemo(() => (api.speech ? createVoice(api.speech) : undefined), [api]);

  useEffect(() => {
    let live = true;
    api.getPersonas().then((r) => {
      if (!live) return;
      setPersonas(r.personas);
      if (r.errors?.length) setPersonaError(r.errors.join("; "));
    }).catch((e) => live && setPersonaError(e instanceof Error ? e.message : "Persona file failed to load"));
    api.getProfiles().then((p) => live && setProfiles(p)).catch(() => undefined);
    return () => { live = false; };
  }, [api]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const newCase = () => {
    if (timer.current) clearTimeout(timer.current);
    forgetSession();
    store.setView(null);
    setAppealBase(null); setMessage(null); setBusy(false);
    setSecurity(null); setAllocation(""); setRequestText("");
  };

  // A returning investor does not configure anything again: the last profile used on this device is reselected.
  useEffect(() => {
    if (selected !== "") return;
    // First visit: the first persona (Robert) is ready, so a hearing can start straight away.
    const id = remembered() || personas[0]?.id || "";
    const p = personas.find((x) => x.id === id);
    const c = profiles.find((x) => x.profile_id === id);
    if (p) { setSelected(id); setValues(valuesFromPersona(p)); }
    else if (c) { setSelected(id); setValues(c.values); }
  }, [personas, profiles, selected]);

  const alloc = parseAllocation(allocation);
  // The structured request is turned into the sentence the deterministic parser reads; no model call is involved.
  const structured = security && alloc.ok ? `Should I put ${alloc.value}% of my portfolio in ${security.ticker}?` : null;
  const request = structured ?? requestText.trim();
  const hasProfile = selected !== "" || values.horizon_min !== null;

  const pick = (id: string) => {
    setSelected(id);
    remember(id);
    const p = personas.find((x) => x.id === id);
    if (p) { setValues(valuesFromPersona(p)); return; }
    const c = profiles.find((x) => x.profile_id === id);
    if (c) setValues(c.values);
  };

  const poll = useCallback((id: string, since = Date.now()) => {
    timer.current = setTimeout(async () => {
      try {
        const v = await api.getSession(id);
        store.setView(v);
        if (v.status === "running") {
          if (Date.now() - since > MAX_WAIT_MS) {
            // Never leave the page loading for ever: release the form and say what happened.
            setBusy(false); forgetSession();
            setMessage("This hearing is taking much longer than usual and may have stopped. Start a new case to try again.");
          } else poll(id, since);
        } else {
          forgetSession();
          setBusy(false);
          if (v.status === "failed") setMessage(`Session failed at stage "${v.error?.stage ?? v.stage}": ${v.error?.message ?? "unknown error"}`);
        }
      } catch (e) {
        setBusy(false);
        setMessage(`The connection to the tribunal was lost (${e instanceof Error ? e.message : "network error"}). Start a new case to try again.`);
      }
    }, pollMs);
  }, [api, store, pollMs]);

  // A page refresh during a hearing picks the same hearing up again instead of losing it.
  useEffect(() => {
    const id = runningSession();
    if (!id || store.getState().view) return;
    api.getSession(id).then((v) => {
      store.setView(v);
      if (v.status === "running") { setBusy(true); poll(id); } else forgetSession();
    }).catch(forgetSession);
  }, [api, store, poll]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    const parsedHoldings = parseHoldings(holdings);
    if (!parsedHoldings.ok) { setMessage(parsedHoldings.error); return; }
    setBusy(true);
    try {
      const savedProfile = profiles.find((p) => p.profile_id === selected);
      const isProfile = savedProfile !== undefined;
      setAppealBase(null);
      const { session_id } = await api.startSession({
        persona_id: isProfile ? savedProfile.base_persona_id : selected || null,
        profile_id: isProfile ? selected : null,
        values, request_text: request,
        ...(parsedHoldings.value ? { base_portfolio: parsedHoldings.value } : {}),
      });
      store.setView({
        session_id, status: "running", contract: null, stage: STAGES[0], stages_done: [], active_agent: null,
        exhibits: [], verdict: null, ruling: null, rule_results: [], sensitivity: [], trace: [],
        summaries: {}, snapshot: null, data_notices: [], error: null,
      });
      rememberSession(session_id);
      poll(session_id);
    } catch (err) {
      setBusy(false);
      // Inputs stay in component state (Req. 7.20, 7.21).
      if (err instanceof ApiError && err.missing) {
        setMessage(`Please state the ${err.missing === "asset" ? "asset" : "position size"} in your request.`);
      } else {
        setMessage(err instanceof Error ? err.message : "Could not start the session");
      }
    }
  };

  const appeal = async (change: AppealChange) => {
    if (!view) return;
    const original = appealBase?.original ?? view;
    setMessage(null);
    setBusy(true);
    try {
      const { session_id } = await api.startAppeal(original.session_id, change);
      setAppealBase({ original, change });
      store.setView({
        ...original, session_id, status: "running", stage: STAGES[0], stages_done: [], active_agent: null,
        exhibits: [], verdict: null, ruling: null, rule_results: [], sensitivity: [], trace: [], error: null,
      });
      rememberSession(session_id);
      poll(session_id);
    } catch (err) {
      setBusy(false);
      setMessage(err instanceof Error ? err.message : "Could not start the appeal");
    }
  };
  const save = async () => {
    const base = personas.some((p) => p.id === selected) ? selected : null;
    const profile: CustomProfile = {
      profile_id: `custom-${Date.now().toString(36)}`, base_persona_id: base, values,
    };
    try {
      const saved = await api.saveProfile(profile);
      setProfiles((ps) => [...ps, saved]);
      setSelected(saved.profile_id);
      remember(saved.profile_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save the profile");
    }
  };

  const download = async () => {
    if (!view) return;
    const trace = await api.getTrace(view.session_id);
    const url = URL.createObjectURL(new Blob([JSON.stringify(trace, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url; a.download = `trace-${view.session_id}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <Banners view={view} />
      <div className="layout">
        <aside aria-label="Inputs" className="sidebar">
          <div className="card decision">
            <form onSubmit={submit} aria-label="Your decision">
              <div className="section-title">
                <h2>Your decision</h2>
                {(view || message) && <button type="button" className="btn-quiet" onClick={newCase}>New case</button>}
              </div>
              <label>Investor profile{" "}
                <select aria-label="Persona" value={selected} disabled={!!personaError && personas.length === 0}
                  onChange={(e) => pick(e.target.value)}>
                  <option value="">Choose a profile…</option>
                  {personas.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
                  {profiles.map((p) => <option key={p.profile_id} value={p.profile_id}>Custom: {p.profile_id}</option>)}
                </select>
              </label>
              {personaError && <p role="alert" data-testid="persona-error" className="alert">Persona file: {personaError}</p>}
              {hasProfile
                ? <p className="profile-summary" data-testid="profile-summary">{profileSummary(values)}</p>
                : <p className="profile-summary missing" data-testid="profile-missing">Choose a profile, or fill in your own under “Profile and limits”. The tribunal does not assume limits you have not given.</p>}
              <div className="field">
                <span className="field-label" id="sec-label">Stock or ETF</span>
                <SecuritySearch value={security} autoFocus
                  onPick={(s) => { setSecurity(s); if (s) setTimeout(() => allocationInput.current?.focus(), 0); }} />
              </div>
              <label>Portfolio allocation{" "}
                <span className="unit-input">
                  <input ref={allocationInput} aria-label="Portfolio allocation (%)" type="text" inputMode="decimal" autoComplete="off"
                    placeholder="e.g. 30" value={allocation} aria-invalid={!alloc.ok && alloc.error !== null}
                    aria-describedby="alloc-help" onChange={(e) => setAllocation(e.target.value)} />
                  <span aria-hidden="true">%</span>
                </span>
                <small id="alloc-help" role={!alloc.ok && alloc.error ? "alert" : undefined}>
                  {!alloc.ok && alloc.error ? alloc.error : ""}
                </small>
              </label>
              <button type="submit" className="btn-enter" disabled={busy || !request || !hasProfile}>
                {busy ? "The tribunal is in session…" : "Enter the Tribunal"}
              </button>
              <details className="own-words">
                <summary>Ask in your own words instead</summary>
                <label>Your question{" "}
                  <textarea aria-label="Request" value={requestText} onChange={(e) => setRequestText(e.target.value)}
                    placeholder="e.g. Should I put 30% of my portfolio in Tesla?" />
                </label>
              </details>
            </form>
          </div>
          <details className="card profile-card" open={!hasProfile || undefined}>
            <summary><h2>Profile and limits</h2></summary>
            <ProfileForm values={values} onChange={setValues} fromProfile={selected !== ""} />
            <HoldingsField text={holdings} onChange={setHoldings} />
            <button type="button" onClick={save} style={{ width: "100%" }}>Save this profile</button>
          </details>
          <div className="card">
            <div role="group" aria-label="Mode" className="mode-switch">
              <button type="button" aria-pressed={mode === "friendly"} onClick={() => store.setMode("friendly")}>Friendly</button>
              <button type="button" aria-pressed={mode === "advanced"} onClick={() => store.setMode("advanced")}>Advanced</button>
            </div>
          </div>
        </aside>
        <div>
          {message && <p role="alert" data-testid="error-message" className="alert">{message}</p>}
          {!view && (
            <div className="card intro" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
              <h1>Should this investment be in your portfolio?</h1>
              <p style={{ color: "var(--muted)", maxWidth: 560, margin: "0 auto" }}>
                Pick a stock or ETF and the share of your portfolio you have in mind. A defense and a prosecution argue
                the case against your own limits, and a judge rules. Every number comes from evidence you can open.
              </p>
            </div>
          )}
          {view && (
            <main>
              {view.status === "running" && appealBase && appealBase.original.session_id !== view.session_id && (
                <p className="pill pill-gold" data-testid="appeal-pending"><span className="dot" />
                  The court is hearing your appeal. The original ruling stands until the new one is in.</p>
              )}
              {view.data_notices.map((n, i) => <p key={i} className="pill pill-warn">{n}</p>)}
              {mode === "advanced"
                ? <AdvancedMode view={view} focus={focus} onFocus={store.setFocus} />
                : <FriendlyMode view={view} onSeeDetails={store.openDetails} speak={speak} inlineExhibits />}
              {view.status === "completed" && appealBase && appealBase.original.session_id !== view.session_id && (
                <div className="card"><AppealView original={appealBase.original} appeal={view} change={appealBase.change} /></div>
              )}
              {view.status === "completed" && <div className="card"><AppealControl busy={busy} onSubmit={appeal} view={view} /></div>}
              {view.status === "completed" && (
                <div className="row" style={{ marginTop: "1rem" }}>
                  <button type="button" onClick={download}>Download trace JSON</button>
                </div>
              )}
            </main>
          )}
        </div>
      </div>
    </div>
  );
}

const Brand = () => (
  <div className="brand"><span>VERDICT<small>Investment decisions, argued and ruled on evidence</small></span></div>
);

/** With `auth`, the workspace sits behind sign-in. Without it (public demonstration) it opens directly. */
export function App({ auth, makeApi }: { auth?: AuthService; makeApi: () => SessionApi }) {
  const [api] = useState(makeApi);
  if (!auth) {
    return (
      <div className="shell">
        <nav className="topbar"><Brand /><p className="user-chip" style={{ margin: 0 }} data-testid="guest-chip">Guest session</p></nav>
        <Workspace api={api} />
      </div>
    );
  }
  return (
    <SignInGate auth={auth}>
      {(user, signOut) => (
        <div className="shell">
          <nav className="topbar">
            <Brand />
            <p className="user-chip" style={{ margin: 0 }}>
              <span className="user-id" title={user}>Signed in as {user}</span>
              <button type="button" onClick={() => { sessionStore.setView(null); signOut(); }}>Sign out</button>
            </p>
          </nav>
          <Workspace api={api} />
        </div>
      )}
    </SignInGate>
  );
}
