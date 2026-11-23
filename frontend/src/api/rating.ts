import { apiJson, queryString } from "./client";
import type { Board, Entry } from "./types";

export function contestLeaderboard(
  contestId: string,
  page: number,
  size: number,
): Promise<Board> {
  return apiJson<Board>(`/contests/${contestId}/leaderboard${queryString({ page, size })}`);
}

export function globalRating(page: number, size: number): Promise<Board> {
  return apiJson<Board>(`/rating/global${queryString({ page, size })}`);
}

export function myRating(contestId?: string): Promise<Entry | null> {
  return apiJson<Entry | null>(`/rating/me${queryString({ contest_id: contestId })}`, {
    auth: true,
  });
}
