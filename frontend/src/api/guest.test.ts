import { describe, expect, it } from "vitest";
import { guestId, guestToken } from "./guest";
import { loadConfig } from "./client";

describe("guest access", () => {
  it("keeps one random 128-bit id per browser and sends it as the Authorization value", async () => {
    localStorage.clear();
    const id = guestId();
    expect(id).toMatch(/^[0-9a-f]{32}$/);
    expect(guestId()).toBe(id);
    expect(await guestToken()).toBe(`Guest ${id}`);
    localStorage.clear();
    expect(guestId()).not.toBe(id);
  });

  it("accepts a guest config without Cognito identifiers", async () => {
    const f = async () => new Response(JSON.stringify({ apiUrl: "https://api.example", guest: true }), { status: 200 });
    expect((await loadConfig(f as typeof fetch)).guest).toBe(true);
  });
});
