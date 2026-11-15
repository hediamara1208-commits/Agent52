// Replay_Mode (Req. 35.3-35.5): renders a recorded SessionView with no network call and no sign-in.
import { useState } from "react";
import { AdvancedMode } from "../advanced";
import { FriendlyMode } from "../friendly";
import { createSessionStore, useSessionStore, type SessionStore, type SessionView } from "../model/sessionView";
import recorded from "./recorded_session.json";

export const REPLAY_LABEL = "Replay of a recorded session";

export function ReplayApp({ view = recorded as unknown as SessionView, store }: {
  view?: SessionView; store?: SessionStore;
}) {
  const [own] = useState(() => store ?? createSessionStore({ view }));
  const { mode, focus } = useSessionStore(own);
  const snap = view.snapshot;
  return (
    <div className="shell">
      <nav className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">⚖</span>
          <span>Decision Tribunal<small>Recorded session replay</small></span>
        </div>
      </nav>
      <header className="banners">
        <p role="note" data-testid="replay-label" className="pill pill-gold"><span className="dot" />
          {REPLAY_LABEL} · session date {snap?.retrieved_at ?? "unknown"} · Snapshot_Id {snap?.snapshot_id ?? "unknown"}
        </p>
        <p role="note" data-testid="simulation-banner" className="pill">Simulation only. This is not financial advice.</p>
        <p role="note" data-testid="guidance-statement" className="pill">
          This tool only provides guidance. You act personally, outside this tool.
        </p>
      </header>
      <div role="group" aria-label="Mode" className="mode-switch" style={{ maxWidth: 320, marginBottom: "1rem" }}>
        <button type="button" aria-pressed={mode === "friendly"} onClick={() => own.setMode("friendly")}>Friendly</button>
        <button type="button" aria-pressed={mode === "advanced"} onClick={() => own.setMode("advanced")}>Advanced</button>
      </div>
      <main>
        {mode === "advanced"
          ? <AdvancedMode view={view} focus={focus} onFocus={own.setFocus} />
          : <FriendlyMode view={view} onSeeDetails={own.openDetails} />}
      </main>
    </div>
  );
}

export function isReplay(search: string, mode: string): boolean {
  return mode === "replay" || new URLSearchParams(search).get("replay") === "1";
}
