import { apiJson } from "./client";
import type { TelegramLink, TelegramLinkStatus } from "./types";

export function telegramStatus(): Promise<TelegramLinkStatus> {
  return apiJson<TelegramLinkStatus>("/telegram/status", { auth: true });
}

export function linkTelegram(): Promise<TelegramLink> {
  return apiJson<TelegramLink>("/telegram/link", { method: "POST", auth: true });
}
