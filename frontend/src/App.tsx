import { useCallback, useEffect, useRef, useState } from "react";
import { AdvancedMode } from "./advanced";
import { FriendlyMode } from "./friendly";
import { ApiError, type ContractValues, type CustomProfile, type PersonaEntry, type SessionApi } from "./api/client";
import type { AuthService } from "./api/auth";
import { sessionStore, useSessionStore, type SessionStore, type SessionView } from "./model/sessionView";
import { AppealControl, AppealView, type AppealChange } from "./appeal";
import { EMPTY_VALUES, ProfileForm, valuesFromPersona } from "./ProfileForm";
import { SignInGate } from "./SignInGate";

export const POLL_MS = 2000;
export const STAGES = ["advocate", "investigator", "judge", "clerk"];

export function Banners({ view }: { view: SessionView | null }) {
  const snap = view?.snapshot;
  return (
    <header>
      <p role="note" data-testid="simulation-banner">Simulation only. This is not financial advice.</p>
      <p role="note" data-testid="guidance-statement">
        This tool only provides guidance. You act personally, outside this tool.
      </p>
      {snap && (
        <p data-testid="data-badge">
          Data: {snap.snapshot_id} · source {snap.source} · retrieved {snap.retrieved_at}
        </p>
      )}
      {snap?.served_from === "cache_fallback" && (
        <p role="alert" data-testid="fallback-notice">
          Served from the local cache because the primary store was unavailable
          {snap.fallback_cause ? ` (${snap.fallback_cause})` : ""}.
        </p>
      )}
    </header>
  );
}

function Progress({ view }: { view: SessionView }) {
  return (
    <ol aria-label="Stage progress" data-testid="progress">
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
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [appealBase, setAppealBase] = useState<{ original: SessionView; change: AppealChange } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  const pick = (id: string) => {
    setSelected(id);
    const p = personas.find((x) => x.id === id);
    if (p) { setValues(valuesFromPersona(p)); return; }
    const c = profiles.find((x) => x.profile_id === id);
    if (c) setValues(c.values);
  };

  const poll = useCallback((id: string) => {
    timer.current = setTimeout(async () => {
      try {
        const v = await api.getSession(id);
        store.setView(v);
        if (v.status === "running") poll(id);
        else {
          setBusy(false);
          if (v.status === "failed") setMessage(`Session failed at stage "${v.error?.stage ?? v.stage}": ${v.error?.message ?? "unknown error"}`);
        }
      } catch (e) {
        setBusy(false);
        setMessage(e instanceof Error ? e.message : "Polling failed");
      }
    }, pollMs);
  }, [api, store, pollMs]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setBusy(true);
    try {
      const isProfile = profiles.some((p) => p.profile_id === selected);
      setAppealBase(null);
      const { session_id } = await api.startSession({
        persona_id: isProfile ? null : selected || null,
        profile_id: isProfile ? selected : null,
        values, request_text: requestText,
      });
      store.setView({
        session_id, status: "running", contract: null, stage: STAGES[0], stages_done: [], active_agent: null,
        exhibits: [], verdict: null, ruling: null, rule_results: [], sensitivity: [], trace: [],
        summaries: {}, snapshot: null, data_notices: [], error: null,
      });
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
      <aside aria-label="Inputs">
        <label>Persona{" "}
          <select aria-label="Persona" value={selected} disabled={!!personaError && personas.length === 0}
            onChange={(e) => pick(e.target.value)}>
            <option value="">Select…</option>
            {personas.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
            {profiles.map((p) => <option key={p.profile_id} value={p.profile_id}>Custom: {p.profile_id}</option>)}
          </select>
        </label>
        {personaError && <p role="alert" data-testid="persona-error">Persona file: {personaError}</p>}
        <ProfileForm values={values} onChange={setValues} />
        <button type="button" onClick={save}>Save as custom profile</button>
        <form onSubmit={submit}>
          <label>Request{" "}
            <textarea aria-label="Request" value={requestText} onChange={(e) => setRequestText(e.target.value)}
              placeholder="e.g. I want 30% in TSLA" />
          </label>
          <button type="submit" disabled={busy || !requestText.trim()}>Submit request</button>
        </form>
        <div role="group" aria-label="Mode">
          <button type="button" aria-pressed={mode === "friendly"} onClick={() => store.setMode("friendly")}>Friendly</button>
          <button type="button" aria-pressed={mode === "advanced"} onClick={() => store.setMode("advanced")}>Advanced</button>
        </div>
      </aside>
      {message && <p role="alert" data-testid="error-message">{message}</p>}
      {view && (
        <main>
          <Progress view={view} />
          {view.data_notices.map((n, i) => <p key={i}>{n}</p>)}
          {mode === "advanced"
            ? <AdvancedMode view={view} focus={focus} onFocus={store.setFocus} />
            : <FriendlyMode view={view} onSeeDetails={store.openDetails} />}
          {view.status === "completed" && appealBase && appealBase.original.session_id !== view.session_id && (
            <AppealView original={appealBase.original} appeal={view} change={appealBase.change} />
          )}
          {view.status === "completed" && <AppealControl busy={busy} onSubmit={appeal} />}
          {view.status === "completed" && <button type="button" onClick={download}>Download trace JSON</button>}
        </main>
      )}
    </div>
  );
}

export function App({ auth, makeApi }: { auth: AuthService; makeApi: () => SessionApi }) {
  const [api] = useState(makeApi);
  return (
    <SignInGate auth={auth}>
      {(user, signOut) => (
        <>
          <p>Signed in as {user} <button type="button" onClick={() => { sessionStore.setView(null); signOut(); }}>Sign out</button></p>
          <Workspace api={api} />
        </>
      )}
    </SignInGate>
  );
}
