import { describe, expect, it } from "vitest";

import { submitDenial } from "./contestWindow";

const NOW = Date.parse("2026-06-01T12:00:00Z");

describe("submitDenial", () => {
  it("reports a non-active status", () => {
    expect(
      submitDenial(
        { status: "published", start_at: "2026-01-01T00:00:00Z", end_at: "2027-01-01T00:00:00Z" },
        NOW,
      ),
    ).toEqual({ kind: "not_active", status: "published" });
  });

  it("reports a contest that has not started", () => {
    expect(
      submitDenial(
        { status: "active", start_at: "2026-06-02T00:00:00Z", end_at: "2026-06-03T00:00:00Z" },
        NOW,
      ),
    ).toEqual({ kind: "not_started", startAt: "2026-06-02T00:00:00Z" });
  });

  it("reports a finished contest", () => {
    expect(
      submitDenial(
        { status: "active", start_at: "2026-05-01T00:00:00Z", end_at: "2026-05-02T00:00:00Z" },
        NOW,
      ),
    ).toEqual({ kind: "finished", endAt: "2026-05-02T00:00:00Z" });
  });

  it("allows submission inside the window", () => {
    expect(
      submitDenial(
        { status: "active", start_at: "2026-05-01T00:00:00Z", end_at: "2026-07-01T00:00:00Z" },
        NOW,
      ),
    ).toBeNull();
  });
});
