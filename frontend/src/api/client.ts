import { refreshAccessToken } from "@/auth/refresh";
import { getAccessToken, getTokens } from "@/auth/tokenStore";
import { API_BASE } from "./config";
import { ApiError } from "./errors";

export { ApiError } from "./errors";
export { errorMessage } from "./errors";

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
};

function buildBody(body: unknown): BodyInit | undefined {
  if (body === undefined || body === null) {
    return undefined;
  }
  if (body instanceof FormData || body instanceof Blob || typeof body === "string") {
    return body;
  }
  return JSON.stringify(body);
}

async function toError(response: Response): Promise<ApiError> {
  let detail: unknown = response.statusText;
  try {
    const data = (await response.json()) as { detail?: unknown };
    detail = data.detail ?? data;
  } catch {
    // response has no JSON body
  }
  const header = response.headers.get("Retry-After");
  const retryAfter = header ? Number(header) : undefined;
  const message = typeof detail === "string" ? detail : `HTTP ${response.status}`;
  return new ApiError(message, response.status, detail, retryAfter);
}

async function raw(path: string, options: RequestOptions, retried: boolean): Promise<Response> {
  const method = options.method ?? "GET";
  const headers = new Headers({ Accept: "application/json" });
  const body = buildBody(options.body);
  if (body !== undefined && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (options.auth) {
    const token = getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body,
    signal: options.signal,
    credentials: "include",
  });

  if (response.status === 401 && options.auth && !retried && getTokens()) {
    try {
      await refreshAccessToken();
    } catch (error) {
      throw error instanceof ApiError ? error : await toError(response);
    }
    return raw(path, options, true);
  }

  return response;
}

export async function api(path: string, options: RequestOptions = {}): Promise<Response> {
  const response = await raw(path, options, false);
  if (!response.ok) {
    throw await toError(response);
  }
  return response;
}

export async function apiJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await api(path, options);
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function queryString(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const result = search.toString();
  return result ? `?${result}` : "";
}
