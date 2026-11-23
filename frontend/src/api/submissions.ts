import { apiJson, queryString } from "./client";
import type {
  RejudgeResponse,
  SubmissionCreate,
  SubmissionDetail,
  SubmissionListResponse,
  SubmissionStatus,
} from "./types";

export function createSubmission(payload: SubmissionCreate): Promise<SubmissionDetail> {
  return apiJson<SubmissionDetail>("/submissions", { method: "POST", auth: true, body: payload });
}

export function getSubmission(submissionId: string): Promise<SubmissionDetail> {
  return apiJson<SubmissionDetail>(`/submissions/${submissionId}`, { auth: true });
}

export function listSubmissions(params: {
  userId?: string;
  problemId?: string;
  status?: SubmissionStatus;
  page?: number;
  size?: number;
}): Promise<SubmissionListResponse> {
  const query = queryString({
    user_id: params.userId,
    problem_id: params.problemId,
    status: params.status,
    page: params.page,
    size: params.size,
  });
  return apiJson<SubmissionListResponse>(`/submissions${query}`, { auth: true });
}

export function rejudgeSubmission(submissionId: string): Promise<RejudgeResponse> {
  return apiJson<RejudgeResponse>(`/submissions/${submissionId}/rejudge`, {
    method: "POST",
    auth: true,
  });
}
