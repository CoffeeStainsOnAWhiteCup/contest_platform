import { apiJson } from "./client";
import type {
  ProblemDetail,
  ProblemUpdate,
  TestCreate,
  TestRead,
  TestUpdate,
} from "./types";

export function getProblem(problemId: string): Promise<ProblemDetail> {
  return apiJson<ProblemDetail>(`/problems/${problemId}`, { auth: true });
}

export function updateProblem(problemId: string, payload: ProblemUpdate): Promise<ProblemDetail> {
  return apiJson<ProblemDetail>(`/problems/${problemId}`, {
    method: "PATCH",
    auth: true,
    body: payload,
  });
}

export function deleteProblem(problemId: string): Promise<void> {
  return apiJson<void>(`/problems/${problemId}`, { method: "DELETE", auth: true });
}

export function listTests(problemId: string): Promise<TestRead[]> {
  return apiJson<TestRead[]>(`/problems/${problemId}/tests`, { auth: true });
}

export function createTest(problemId: string, payload: TestCreate): Promise<TestRead> {
  return apiJson<TestRead>(`/problems/${problemId}/tests`, {
    method: "POST",
    auth: true,
    body: payload,
  });
}

export function updateTest(
  problemId: string,
  testId: string,
  payload: TestUpdate,
): Promise<TestRead> {
  return apiJson<TestRead>(`/problems/${problemId}/tests/${testId}`, {
    method: "PATCH",
    auth: true,
    body: payload,
  });
}

export function deleteTest(problemId: string, testId: string): Promise<void> {
  return apiJson<void>(`/problems/${problemId}/tests/${testId}`, {
    method: "DELETE",
    auth: true,
  });
}

export function importTests(problemId: string, file: File): Promise<{ imported: number }> {
  const form = new FormData();
  form.append("file", file);
  return apiJson<{ imported: number }>(`/problems/${problemId}/tests/import`, {
    method: "POST",
    auth: true,
    body: form,
  });
}
