import type { ContestStatus } from "@/api/types";

export type SubmitWindow = {
  status: ContestStatus;
  start_at: string;
  end_at: string;
};

export type SubmitDenial =
  | { kind: "not_active"; status: ContestStatus }
  | { kind: "not_started"; startAt: string }
  | { kind: "finished"; endAt: string };

/**
 * Mirror the backend rule (app/modules/contests/policy.py): submissions are
 * accepted only while the contest is active and the current time is inside the
 * start/end interval.
 */
export function submitDenial(contest: SubmitWindow, now: number = Date.now()): SubmitDenial | null {
  if (contest.status !== "active") {
    return { kind: "not_active", status: contest.status };
  }
  if (now < Date.parse(contest.start_at)) {
    return { kind: "not_started", startAt: contest.start_at };
  }
  if (now > Date.parse(contest.end_at)) {
    return { kind: "finished", endAt: contest.end_at };
  }
  return null;
}

export function contestPhase(contest: SubmitWindow, now: number) {
  const denial = submitDenial(contest, now);
  if (denial?.kind === "not_started") return "scheduled";
  if (denial?.kind === "finished") return "finished";
  return contest.status;
}
