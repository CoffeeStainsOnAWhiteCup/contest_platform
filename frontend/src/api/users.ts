import { apiJson, queryString } from "./client";
import type { AdminView, Profile, UserRole } from "./types";

export function getMe(): Promise<Profile> {
  return apiJson<Profile>("/users/me", { auth: true });
}

export function updateProfile(payload: {
  name?: string;
  avatar_url?: string | null;
}): Promise<Profile> {
  return apiJson<Profile>("/users/me", { method: "PATCH", auth: true, body: payload });
}

export function listUsers(page: number, size: number): Promise<AdminView[]> {
  return apiJson<AdminView[]>(`/users${queryString({ page, size })}`, { auth: true });
}

export function changeRole(userId: string, role: UserRole): Promise<AdminView> {
  return apiJson<AdminView>(`/users/${userId}/role`, {
    method: "PATCH",
    auth: true,
    body: { role },
  });
}

export function changeBlock(userId: string, isBlocked: boolean): Promise<AdminView> {
  return apiJson<AdminView>(`/users/${userId}/block`, {
    method: "PATCH",
    auth: true,
    body: { is_blocked: isBlocked },
  });
}
