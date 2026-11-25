import { useEffect, useState } from "react";

import type { SubmitWindow } from "./contestWindow";

/** Refresh open pages when a contest crosses a boundary, including after tab sleep. */
export function useContestTime(contests: SubmitWindow | SubmitWindow[] | undefined) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const windows = Array.isArray(contests) ? contests : contests ? [contests] : [];
    function refresh() {
      clearTimeout(timer);
      const time = Date.now();
      setNow(time);
      const boundaries = windows
        .filter((item) => item.status === "active")
        .flatMap((item) => [Date.parse(item.start_at), Date.parse(item.end_at) + 1]);
      const next = Math.min(...boundaries.filter((value) => value > time));
      if (Number.isFinite(next)) {
        timer = setTimeout(refresh, Math.min(next - time, 2_147_483_647));
      }
    }
    refresh();
    window.addEventListener("focus", refresh);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("focus", refresh);
    };
  }, [contests]);
  return now;
}
