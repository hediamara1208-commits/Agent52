import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Workspace, App } from "./App";
import { createApiClient, loadConfig, type SessionApi } from "./api/client";
import type { AuthService } from "./api/auth";
import { createSessionStore, type SessionView } from "./model/sessionView";

const done: SessionView = {
  session_id: "s1", status: "completed", contract: null, stage: "clerk",
  stages_done: ["advocate", "investigator", "judge", "clerk"], active_agent: null, exhibits: [],
  verdict: null, ruling: null, rule_results: [], sensitivity: [], trace: [], summaries: {},
  snapshot: { snapshot_id: "snap-1", source: "s3", retrieved_at: "2025-01-01T00:00:00Z", coverage_end: "2025-01-01", served_from: "cache_fallback", fallback_cause: "s3 down" },
  data_notices: [], error: null,
};
const persona = {
  id: "robert", display_name: "Robert", risk_level: "low_to_moderate", horizon: 5,
  contract_values: { max_volatility: { value: 0.12 }, horizon_years: { value: 5 } },
};
const fakeApi = (over: Partial<SessionApi> = {}): SessionApi => ({
  getPersonas: async () => ({ personas: [persona] }),
  getProfiles: async () => [],
  saveProfile: async (p) => p,
  startSession: async () => ({ session_id: "s1" }),
  startAppeal: async () => ({ session_id: "s2" }),
  getSession: async () => done,
  getTrace: async () => ({}),
  ...over,
});

describe("sign-in gate", () => {
  it("shows no workspace before sign-in", async () => {
    const auth: AuthService = {
      currentUser: async () => null, signIn: vi.fn(), signOut: vi.fn(), apiToken: async () => null,
    };
    const makeApi = vi.fn(() => fakeApi());
    render(<App auth={auth} makeApi={makeApi} />);
    expect(await screen.findByRole("form", { name: "Sign in" })).toBeTruthy();
    expect(screen.queryByLabelText("Request")).toBeNull();
  });
});

describe("Workspace", () => {
  it("pre-fills from persona, submits, polls to completion, shows badge and fallback notice", async () => {
    const store = createSessionStore();
    render(<Workspace api={fakeApi()} store={store} pollMs={5} />);
    const user = userEvent.setup();
    await screen.findByRole("option", { name: "Robert" });
    await user.selectOptions(screen.getByLabelText("Persona"), "robert");
    expect((screen.getByLabelText(/Max volatility/) as HTMLInputElement).value).toBe("12");
    await user.type(screen.getByLabelText("Request"), "30% in TSLA");
    await user.click(screen.getByRole("button", { name: "Enter the Tribunal" }));
    await waitFor(() => expect(screen.getByTestId("data-badge").textContent).toContain("snap-1"));
    expect(screen.getByTestId("fallback-notice")).toBeTruthy();
    expect(screen.getByTestId("simulation-banner")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Advanced" }));
    expect(screen.getByTestId("advanced-mode")).toBeTruthy();
    expect(screen.getByTestId("guidance-statement")).toBeTruthy();
  });

  it("starts a hearing from a security and an allocation in two clicks, reusing the remembered profile", async () => {
    localStorage.setItem("verdict.lastProfile", "robert");
    const startSession = vi.fn(async () => ({ session_id: "s1" }));
    render(<Workspace api={fakeApi({ startSession })} store={createSessionStore()} pollMs={5} />);
    const user = userEvent.setup();
    expect(await screen.findByTestId("profile-summary")).toHaveTextContent("5-year horizon");
    const search = screen.getByRole("combobox", { name: "Stock or ETF" });
    expect(search).toHaveFocus();
    await user.keyboard("tesla");
    await user.click(screen.getByRole("option", { name: /Tesla/ }));          // click 1
    expect(screen.getByLabelText("Portfolio allocation (%)")).toHaveFocus();
    await user.keyboard("30");
    await user.click(screen.getByRole("button", { name: "Enter the Tribunal" })); // click 2
    expect(startSession).toHaveBeenCalledWith(expect.objectContaining({ persona_id: "robert", request_text: "Should I put 30% of my portfolio in TSLA?" }));
    localStorage.clear();
  });

  it("offers nothing for a security outside the dataset and refuses impossible allocations", async () => {
    localStorage.setItem("verdict.lastProfile", "robert");
    render(<Workspace api={fakeApi()} store={createSessionStore()} />);
    const user = userEvent.setup();
    await screen.findByTestId("profile-summary");
    await user.keyboard("SpaceX");
    expect(screen.getByTestId("security-none")).toHaveTextContent("not among the 31 securities");
    expect(screen.getByRole("button", { name: "Enter the Tribunal" })).toBeDisabled();
    await user.clear(screen.getByRole("combobox", { name: "Stock or ETF" }));
    await user.keyboard("apple{Enter}150");
    expect(screen.getByRole("alert")).toHaveTextContent("cannot exceed 100%");
    expect(screen.getByRole("button", { name: "Enter the Tribunal" })).toBeDisabled();
    localStorage.clear();
  });

  it("asks for a profile instead of assuming limits", async () => {
    localStorage.clear();
    render(<Workspace api={fakeApi()} store={createSessionStore()} />);
    const user = userEvent.setup();
    await screen.findByRole("option", { name: "Robert" });
    await user.keyboard("tesla{Enter}30");
    expect(screen.getByTestId("profile-missing")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enter the Tribunal" })).toBeDisabled();
  });

  it("disables the picker and shows the error when the Persona_File fails", async () => {
    const api = fakeApi({ getPersonas: async () => { throw new Error("bad yaml"); } });
    render(<Workspace api={api} store={createSessionStore()} />);
    expect((await screen.findByTestId("persona-error")).textContent).toContain("bad yaml");
    expect((screen.getByLabelText("Persona") as HTMLSelectElement).disabled).toBe(true);
  });

  it("keeps the request text and asks for the missing asset on a parse error", async () => {
    const { ApiError } = await import("./api/client");
    const api = fakeApi({ startSession: async () => { throw new ApiError(422, "cannot parse", "asset"); } });
    render(<Workspace api={api} store={createSessionStore()} />);
    const user = userEvent.setup();
    await screen.findByRole("option", { name: "Robert" });
    await user.selectOptions(screen.getByLabelText("Persona"), "robert");
    await user.type(screen.getByLabelText("Request"), "invest some");
    await user.click(screen.getByRole("button", { name: "Enter the Tribunal" }));
    expect((await screen.findByTestId("error-message")).textContent).toContain("asset");
    expect((screen.getByLabelText("Request") as HTMLTextAreaElement).value).toBe("invest some");
  });
});

describe("api client", () => {
  it("sends the access token and rejects without one", async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ personas: [] }), { status: 200 }));
    const c = createApiClient({ apiUrl: "https://api.example/" }, async () => "tok", f as unknown as typeof fetch);
    await c.getPersonas();
    expect(f).toHaveBeenCalledWith("https://api.example/personas", expect.objectContaining({ headers: { Authorization: "tok" } }));
    const none = createApiClient({ apiUrl: "x" }, async () => null, f as unknown as typeof fetch);
    await expect(none.getPersonas()).rejects.toThrow("Not signed in");
  });
  it("loadConfig requires the identifiers", async () => {
    const f = async () => new Response(JSON.stringify({ apiUrl: "" }), { status: 200 });
    await expect(loadConfig(f as unknown as typeof fetch)).rejects.toThrow("missing");
  });
});

describe("Session_API request body", () => {
  it("wraps the persona and form values in a profile object", async () => {
    const { createApiClient } = await import("./api/client");
    const f = vi.fn(async () => new Response(JSON.stringify({ session_id: "s1" }), { status: 202 }));
    const api = createApiClient({ apiUrl: "https://api.example" }, async () => "tok", f as unknown as typeof fetch);
    const values = { risk_level: "low", horizon_min: null, horizon_max: null, max_volatility: 0.12, max_drawdown: 0.15,
      per_asset_cap: 0.1, crypto_cap: 0.02, esg_exclusions: [] };
    await api.startSession({ persona_id: "robert", profile_id: null, values, request_text: "30% in TSLA" });
    const init = (f.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(JSON.parse(String(init.body))).toEqual({
      profile: { base_persona_id: "robert", values }, request_text: "30% in TSLA",
    });
  });
});

describe("Session_API missing fields", () => {
  it("maps {asset: true} to the 'asset' hint", async () => {
    const { createApiClient, ApiError } = await import("./api/client");
    const f = vi.fn(async () => new Response(JSON.stringify({ error: "request is missing fields", missing: { asset: true, size: false } }), { status: 422 }));
    const api = createApiClient({ apiUrl: "https://api.example" }, async () => "tok", f as unknown as typeof fetch);
    const err = await api.startSession({ persona_id: "robert", profile_id: null, values: {} as never, request_text: "30% in x" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.missing).toBe("asset");
  });
});
