/**
 * Thin fetch wrapper around the FastAPI backend's {data, error} envelope
 * (see backend docs/04-api-specification.md). Used from both Server
 * Components (build-time-safe, no browser globals) and Client Components.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export { API_BASE_URL };

type ApiEnvelope<T> = { data: T | null; error: { code: string; message: string } | null };

/** Raw Response, for callers that need status/headers directly (e.g. the
 * admin auth client's 401-then-refresh-then-retry logic). */
export async function rawRequest(path: string, init?: RequestInit & { cache?: RequestCache }): Promise<globalThis.Response> {
  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    // The backend is the source of truth for donation/event state — never
    // let Next.js serve a stale cached response for these calls.
    cache: init?.cache ?? "no-store",
    // Required for the refresh_token httpOnly cookie to flow on cross-origin
    // requests between the frontend (:3000) and backend (:8000) origins in
    // dev — the backend's CORS config already sets Access-Control-Allow-
    // Credentials: true for exactly this. See docs/05-architecture.md.
    credentials: init?.credentials ?? "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
}

export async function unwrapEnvelope<T>(response: globalThis.Response): Promise<T> {
  let envelope: ApiEnvelope<T>;
  try {
    envelope = (await response.json()) as ApiEnvelope<T>;
  } catch {
    throw new ApiError("INTERNAL_ERROR", "The server returned an unexpected response.", response.status);
  }

  if (!response.ok || envelope.error) {
    throw new ApiError(
      envelope.error?.code ?? "INTERNAL_ERROR",
      envelope.error?.message ?? "Something went wrong. Please try again.",
      response.status,
    );
  }

  return envelope.data as T;
}

async function request<T>(path: string, init?: RequestInit & { cache?: RequestCache }): Promise<T> {
  const response = await rawRequest(path, init);
  return unwrapEnvelope<T>(response);
}

export const apiClient = {
  get: <T>(path: string, init?: RequestInit) => request<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, { ...init, method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown, init?: RequestInit) =>
    request<T>(path, { ...init, method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string, init?: RequestInit) => request<T>(path, { ...init, method: "DELETE" }),
};
