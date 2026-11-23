import { apiJson, queryString } from "./client";
import type {
  ContestCreate,
  ContestDetail,
  ContestListResponse,
  ContestRead,
  ContestStatus,
  ContestUpdate,
  ProblemCreate,
  ProblemDetail,
} from "./types";

export function listContests(params: {
  status?: ContestStatus;
  page?: number;
  size?: number;
}): Promise<ContestListResponse> {
  return apiJson<ContestListResponse>(`/contests${queryString(params)}`);
}

export function getContest(contestId: string): Promise<ContestDetail> {
  return apiJson<ContestDetail>(`/contests/${contestId}`);
}

export function createContest(payload: ContestCreate): Promise<ContestRead> {
  return apiJson<ContestRead>("/contests", { method: "POST", auth: true, body: payload });
}

export function updateContest(contestId: string, payload: ContestUpdate): Promise<ContestRead> {
  return apiJson<ContestRead>(`/contests/${contestId}`, {
    method: "PATCH",
    auth: true,
    body: payload,
  });
}

export function deleteContest(contestId: string): Promise<void> {
  return apiJson<void>(`/contests/${contestId}`, { method: "DELETE", auth: true });
}

export function createProblem(contestId: string, payload: ProblemCreate): Promise<ProblemDetail> {
  return apiJson<ProblemDetail>(`/contests/${contestId}/problems`, {
    method: "POST",
    auth: true,
    body: payload,
  });
}
