import { apiJson } from "./client";
import type { TelegramLink } from "./types";

export function linkTelegram(): Promise<TelegramLink> {
  return apiJson<TelegramLink>("/telegram/link", { method: "POST", auth: true });
}
