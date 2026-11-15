import { describe, it, expect, vi } from "vitest";
import { parseHoldings } from "./ProfileForm";
import { createApiClient } from "./api/client";

describe("current holdings (custom Base_Portfolio)", () => {
  it("reads 'ticker weight' pairs in percent or fractions", () => {
    expect(parseHoldings("XIU.TO 40, RY.TO 15, TD.TO 10, ENB.TO 10, XBB.TO 25")).toEqual({
      ok: true, value: { "XIU.TO": 40, "RY.TO": 15, "TD.TO": 10, "ENB.TO": 10, "XBB.TO": 25 },
    });
    expect(parseHoldings("xiu.to: 0.6; xbb.to=0.4")).toEqual({ ok: true, value: { "XIU.TO": 0.6, "XBB.TO": 0.4 } });
    expect(parseHoldings("  ")).toEqual({ ok: true, value: null });
  });

  it("explains what is wrong", () => {
    const sum = parseHoldings("XIU.TO 40, XBB.TO 40");
    expect(sum.ok).toBe(false);
    if (!sum.ok) expect(sum.error).toContain("80.0%");
    const bad = parseHoldings("XIU.TO forty");
    expect(bad.ok).toBe(false);
    const dup = parseHoldings("SPY 50, spy 50");
    expect(dup.ok).toBe(false);
  });

  it("sends the holdings next to the profile values, not inside them", async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ session_id: "s1" }), { status: 202 }));
    const api = createApiClient({ apiUrl: "https://api.example" }, async () => "tok", f as unknown as typeof fetch);
    await api.startSession({ persona_id: "robert", profile_id: null, values: {} as never,
      request_text: "Would adding 10% SPY improve diversification?", base_portfolio: { "XIU.TO": 60, "XBB.TO": 40 } });
    const body = JSON.parse(String((f.mock.calls[0] as unknown as [string, RequestInit])[1].body));
    expect(body.profile.base_portfolio).toEqual({ "XIU.TO": 60, "XBB.TO": 40 });
    expect(body.profile.values.base_portfolio).toBeUndefined();
  });
});
