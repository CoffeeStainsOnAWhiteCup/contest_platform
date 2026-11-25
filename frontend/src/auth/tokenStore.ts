import { storage } from "@/lib/storage";

export type Tokens = {
  access: string;
  refresh: string;
};

const ACCESS_KEY = "contest.access_token";
const REFRESH_KEY = "contest.refresh_token";
const SIGN_IN_KEY = "contest.sign_in";
const CHANNEL_NAME = "contest-auth";

type Listener = () => void;

const listeners = new Set<Listener>();

const channel: BroadcastChannel | null =
  typeof window !== "undefined" && typeof window.BroadcastChannel === "function"
    ? new BroadcastChannel(CHANNEL_NAME)
    : null;

if (channel) {
  channel.onmessage = () => notify();
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    // A new sign-in in another tab replaces the profile and its cached private data.
    if (event.key === SIGN_IN_KEY) {
      window.location.reload();
      return;
    }
    if (event.key === ACCESS_KEY || event.key === REFRESH_KEY) {
      notify();
    }
  });
}

function notify(): void {
  for (const listener of listeners) {
    listener();
  }
}

export function subscribeAuth(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getTokens(): Tokens | null {
  const access = storage.getItem(ACCESS_KEY);
  const refresh = storage.getItem(REFRESH_KEY);
  if (!access || !refresh) {
    return null;
  }
  return { access, refresh };
}

export function getAccessToken(): string | null {
  return storage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return storage.getItem(REFRESH_KEY);
}

export function setTokens(tokens: Tokens): void {
  storage.setItem(ACCESS_KEY, tokens.access);
  storage.setItem(REFRESH_KEY, tokens.refresh);
  channel?.postMessage("update");
  notify();
}

export function startLocalSession(tokens: Tokens): void {
  setTokens(tokens);
  storage.setItem(SIGN_IN_KEY, String(Date.now()));
}

export function clearTokens(): void {
  storage.removeItem(ACCESS_KEY);
  storage.removeItem(REFRESH_KEY);
  channel?.postMessage("clear");
  notify();
}
