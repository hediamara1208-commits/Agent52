// View store for the SPA. Types come from session_view.schema.json (npm run gen:types).
// The store holds the server SessionView plus browser-only `mode` and `focus` (Req. 7.14).
import { useSyncExternalStore } from "react";
import type { SessionView } from "./sessionView.types";

export type {
  SessionView, Exhibit, Verdict, Ruling, Statement, Answer, RuleResult,
  SensitivityResult, TraceEvent, Snapshot, StageError, NewsItem,
} from "./sessionView.types";

export type Mode = "friendly" | "advanced";

export type Focus =
  | { kind: "exhibit"; number: number }
  | { kind: "rule"; rule: string }
  | { kind: "trace"; seq: number };

export interface ViewState {
  view: SessionView | null;
  mode: Mode;
  focus: Focus | null;
}

export interface SessionStore {
  getState(): ViewState;
  subscribe(listener: () => void): () => void;
  setView(view: SessionView | null): void;
  /** Changes only `mode`; never calls the API (Req. 7.14). */
  setMode(mode: Mode): void;
  setFocus(focus: Focus | null): void;
  /** "See details": set focus and switch to Advanced_Mode (Req. 7.17). */
  openDetails(focus: Focus): void;
}

export function createSessionStore(initial?: Partial<ViewState>): SessionStore {
  let state: ViewState = { view: null, mode: "friendly", focus: null, ...initial };
  const listeners = new Set<() => void>();
  const set = (patch: Partial<ViewState>) => {
    state = { ...state, ...patch };
    listeners.forEach((l) => l());
  };
  return {
    getState: () => state,
    subscribe(l) {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    setView: (view) => set({ view }),
    setMode: (mode) => set({ mode }),
    setFocus: (focus) => set({ focus }),
    openDetails: (focus) => set({ focus, mode: "advanced" }),
  };
}

export const sessionStore = createSessionStore();

export function useSessionStore(store: SessionStore = sessionStore): ViewState {
  return useSyncExternalStore(store.subscribe, store.getState, store.getState);
}
