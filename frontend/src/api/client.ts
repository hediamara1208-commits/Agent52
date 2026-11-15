// Session_API client (Req. 22.2). Access token comes from Amplify Auth; API URL and
// Cognito identifiers come from the runtime config.json (no secrets, no baked-in values).
import type { SessionView } from "../model/sessionView";

export interface RuntimeConfig {
  apiUrl: string;
  region?: string;
  userPoolId: string;
  userPoolClientId: string;
}

export async function loadConfig(fetchImpl: typeof fetch = fetch, url = "/config.json"): Promise<RuntimeConfig> {
  const res = await fetchImpl(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`config.json could not be loaded (${res.status})`);
  const cfg = (await res.json()) as Partial<RuntimeConfig>;
  if (!cfg.apiUrl || !cfg.userPoolId || !cfg.userPoolClientId) {
    throw new Error("config.json is missing apiUrl, userPoolId, or userPoolClientId");
  }
  return cfg as RuntimeConfig;
}

export interface ContractValues {
  risk_level: string;
  horizon_min: number | null;
  horizon_max: number | null;
  max_volatility: number | null;
  max_drawdown: number | null;
  per_asset_cap: number | null;
  crypto_cap: number | null;
  esg_exclusions: string[];
}
export interface PersonaEntry {
  id: string;
  display_name: string;
  risk_level: string;
  horizon: number | { min: number; max?: number };
  contract_values: Record<string, { value: unknown } | undefined>;
}
export interface PersonasResponse { personas: PersonaEntry[]; errors?: string[] }
export interface CustomProfile {
  profile_id: string;
  base_persona_id: string | null;
  values: ContractValues;
}
export interface SessionRequest {
  persona_id: string | null;
  profile_id?: string | null;
  values: ContractValues;
  request_text: string;
  /** The investor's current holdings, {ticker: weight}; replaces the persona's Base_Portfolio. */
  base_portfolio?: Record<string, number> | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public missing?: string) {
    super(message);
  }
}

export interface SessionApi {
  getPersonas(): Promise<PersonasResponse>;
  getProfiles(): Promise<CustomProfile[]>;
  saveProfile(profile: CustomProfile): Promise<CustomProfile>;
  startSession(req: SessionRequest): Promise<{ session_id: string }>;
  startAppeal(appealOf: string, change: { field: string; value: unknown }): Promise<{ session_id: string }>;
  getSession(id: string): Promise<SessionView>;
  getTrace(id: string): Promise<unknown>;
  /** Voice one court speech (Amazon Polly); optional so test fakes need not implement it. */
  speech?(speaker: string, text: string): Promise<{ audio: string; content_type: string }>;
}

export function createApiClient(
  config: Pick<RuntimeConfig, "apiUrl">,
  getToken: () => Promise<string | null>,
  fetchImpl: typeof fetch = fetch,
): SessionApi {
  const base = config.apiUrl.replace(/\/+$/, "");
  async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
    const token = await getToken();
    if (!token) throw new ApiError(401, "Not signed in");
    const res = await fetchImpl(`${base}${path}`, {
      method,
      headers: {
        // Raw ID token: the API Gateway Cognito authorizer does not strip a "Bearer " prefix.
        Authorization: token,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      // The API reports missing request fields as {asset: bool, size: bool}; the UI wants one name.
      const m = data?.missing;
      const missing = typeof m === "string" ? m : m && typeof m === "object" ? (m.asset ? "asset" : m.size ? "size" : undefined) : undefined;
      throw new ApiError(res.status, data?.message ?? data?.error ?? `Request failed (${res.status})`, missing);
    }
    return data as T;
  }
  return {
    getPersonas: () => call("GET", "/personas"),
    getProfiles: async () => {
      const r = await call<CustomProfile[] | { profiles: CustomProfile[] }>("GET", "/profiles");
      return Array.isArray(r) ? r : r.profiles;
    },
    saveProfile: (p) => call("PUT", `/profiles/${encodeURIComponent(p.profile_id)}`, p),
    // Session_API body (api/handler.py): {profile: {base_persona_id, values, profile_id?}, request_text}.
    startSession: (r) => call("POST", "/sessions", {
      profile: {
        base_persona_id: r.persona_id,
        values: r.values,
        ...(r.profile_id ? { profile_id: r.profile_id } : {}),
        ...(r.base_portfolio ? { base_portfolio: r.base_portfolio } : {}),
      },
      request_text: r.request_text,
    }),
    startAppeal: (appeal_of, change) => call("POST", "/sessions", { appeal_of, change }),
    getSession: (id) => call("GET", `/sessions/${encodeURIComponent(id)}`),
    getTrace: (id) => call("GET", `/sessions/${encodeURIComponent(id)}/trace`),
    speech: (speaker, text) => call("POST", "/speech", { speaker, text }),
  };
}
