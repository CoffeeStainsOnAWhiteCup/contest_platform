import { act, renderHook } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { contestPhase } from "./contestWindow";
import { useContestTime } from "./useContestTime";

it("updates a mounted contest at start and immediately after its inclusive deadline", () => {
  vi.useFakeTimers();
  const start = Date.parse("2026-11-25T11:12:02Z");
  const contest = {
    status: "active" as const,
    start_at: new Date(start).toISOString(),
    end_at: new Date(start + 600_000).toISOString(),
  };
  try {
    vi.setSystemTime(start - 1000);
    const { result, unmount } = renderHook(() => contestPhase(contest, useContestTime(contest)));
    expect(result.current).toBe("scheduled");
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current).toBe("active");
    act(() => vi.advanceTimersByTime(600_000));
    expect(result.current).toBe("active");
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe("finished");
    expect(contestPhase({ ...contest, status: "archived" }, Date.now())).toBe("archived");
    unmount();
  } finally {
    vi.useRealTimers();
  }
});
