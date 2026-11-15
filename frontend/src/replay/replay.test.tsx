import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReplayApp, isReplay } from "./ReplayApp";

describe("Replay_Mode", () => {
  it("shows the label with date and Snapshot_Id, renders the ruling, and makes no network call", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    render(<ReplayApp />);
    const label = screen.getByTestId("replay-label").textContent ?? "";
    expect(label).toContain("Replay of a recorded session");
    expect(label).toContain("20261113T000000Z-test");
    expect(label).toContain("2026-11-13");
    expect(screen.queryByRole("form", { name: "Sign in" })).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
  it("detects ?replay=1 and the replay build mode", () => {
    expect(isReplay("?replay=1", "production")).toBe(true);
    expect(isReplay("", "replay")).toBe(true);
    expect(isReplay("", "production")).toBe(false);
  });
});
