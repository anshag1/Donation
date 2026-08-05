"use client";

/**
 * Admin auth client — native FastAPI JWT, not Better Auth (see
 * docs/05-architecture.md). The access token is short-lived (30 min) and
 * kept in memory + localStorage (read on load so a page refresh doesn't
 * immediately sign the admin out); the refresh token is an httpOnly cookie
 * this code never touches directly.
 *
 * Route protection for /admin/* is deliberately CLIENT-SIDE (AuthProvider +
 * AdminGuard below), not a Next.js proxy.ts server-side gate. Reason: the
 * refresh cookie is set by the backend on a DIFFERENT origin
 * (localhost:8000 vs the frontend's localhost:3000) and scoped to path
 * /api/v1/auth — Next's server (proxy.ts / Server Components) only sees
 * cookies sent to ITS OWN origin on the current request path, so it
 * structurally cannot see this cookie for an /admin/dashboard request.
 * Making that work would mean either rewriting all API calls through a
 * same-origin Next.js proxy AND adding a second, non-path-restricted
 * session-indicator cookie, or building a BFF layer — real options for
 * later, not worth the complexity for this pass. The backend's RBAC checks
 * are the actual security boundary regardless; this is UX, not a security
 * control.
 */

import { API_BASE_URL, ApiError, rawRequest, unwrapEnvelope } from "@/lib/api-client";

const ACCESS_TOKEN_STORAGE_KEY = "donation_admin_access_token";

export interface CurrentAdmin {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  roles: string[];
  two_factor_enabled: boolean;
}

export interface LoginResult {
  mfaRequired: boolean;
  mfaToken?: string;
}

export interface TwoFactorSetup {
  secret: string;
  otpauth_uri: string;
  qr_code_data_uri: string;
}

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  if (accessToken) return accessToken;
  if (typeof window === "undefined") return null;
  accessToken = window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
  return accessToken;
}

function setAccessToken(token: string | null): void {
  accessToken = token;
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  }
}

interface LoginResponseBody {
  access_token: string | null;
  mfa_required: boolean;
  mfa_token: string | null;
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const response = await rawRequest("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const data = await unwrapEnvelope<LoginResponseBody>(response);
  if (data.mfa_required) {
    return { mfaRequired: true, mfaToken: data.mfa_token ?? undefined };
  }
  setAccessToken(data.access_token);
  return { mfaRequired: false };
}

export async function verifyLogin2fa(mfaToken: string, code: string): Promise<void> {
  const response = await rawRequest("/api/v1/auth/login/verify-2fa", {
    method: "POST",
    body: JSON.stringify({ mfa_token: mfaToken, code }),
  });
  const data = await unwrapEnvelope<LoginResponseBody>(response);
  if (!data.access_token) {
    throw new ApiError("UNAUTHORIZED", "Verification failed.", 401);
  }
  setAccessToken(data.access_token);
}

export async function logout(): Promise<void> {
  try {
    await rawRequest("/api/v1/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}

async function tryRefresh(): Promise<boolean> {
  try {
    const response = await rawRequest("/api/v1/auth/refresh", { method: "POST" });
    if (!response.ok) return false;
    const data = await unwrapEnvelope<{ access_token: string }>(response);
    setAccessToken(data.access_token);
    return true;
  } catch {
    return false;
  }
}

/** Authenticated request with one automatic refresh-and-retry on a 401 —
 * mirrors what a real logged-in session should feel like (no surprise
 * logouts every 30 minutes) without a background refresh timer. */
async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const withAuth = (t: string | null) => ({
    ...init,
    headers: { ...init?.headers, ...(t ? { Authorization: `Bearer ${t}` } : {}) },
  });

  let response = await rawRequest(path, withAuth(token));
  if (response.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      response = await rawRequest(path, withAuth(getAccessToken()));
    }
  }
  return unwrapEnvelope<T>(response);
}

/** Multipart file upload (event banners, org logo/signature). Deliberately
 * does NOT set a Content-Type header — the browser must set it itself
 * (including the multipart boundary), which `rawRequest`'s default JSON
 * header would otherwise clobber. */
async function adminUpload<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);

  const doUpload = (token: string | null) =>
    fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: formData,
    });

  let response = await doUpload(getAccessToken());
  if (response.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      response = await doUpload(getAccessToken());
    }
  }
  return unwrapEnvelope<T>(response);
}

/** For endpoints that return a raw file (CSV export, duplicate-receipt PDF)
 * rather than the {data, error} envelope — triggers a browser download. */
async function adminDownload(path: string, init?: RequestInit): Promise<Blob> {
  const token = getAccessToken();
  const withAuth = (t: string | null) => ({
    ...init,
    headers: { ...init?.headers, ...(t ? { Authorization: `Bearer ${t}` } : {}) },
  });

  let response = await rawRequest(path, withAuth(token));
  if (response.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      response = await rawRequest(path, withAuth(getAccessToken()));
    }
  }
  if (!response.ok) {
    throw new ApiError("INTERNAL_ERROR", "Could not download this file.", response.status);
  }
  return response.blob();
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const adminApiClient = {
  get: <T>(path: string) => adminRequest<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    adminRequest<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    adminRequest<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => adminRequest<T>(path, { method: "DELETE" }),
  download: (path: string, init?: RequestInit) => adminDownload(path, init),
  upload: <T>(path: string, file: File) => adminUpload<T>(path, file),
};

export async function acceptInvite(token: string, password: string): Promise<void> {
  const response = await rawRequest("/api/v1/auth/accept-invite", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
  await unwrapEnvelope<null>(response);
}

/** Always resolves (the backend returns the same success response whether
 * or not the email is registered, to avoid leaking which admin accounts
 * exist) — the caller should show a generic "check your email" message
 * regardless of the outcome. */
export async function forgotPassword(email: string): Promise<void> {
  const response = await rawRequest("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  await unwrapEnvelope<null>(response);
}

export async function resetPassword(token: string, password: string): Promise<void> {
  const response = await rawRequest("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
  await unwrapEnvelope<null>(response);
}

export function setup2fa(): Promise<TwoFactorSetup> {
  return adminApiClient.post<TwoFactorSetup>("/api/v1/auth/2fa/setup");
}

export function enable2fa(code: string): Promise<void> {
  return adminApiClient.post<void>("/api/v1/auth/2fa/enable", { code });
}

export function disable2fa(code: string): Promise<void> {
  return adminApiClient.post<void>("/api/v1/auth/2fa/disable", { code });
}

export async function fetchCurrentAdmin(): Promise<CurrentAdmin | null> {
  try {
    return await adminApiClient.get<CurrentAdmin>("/api/v1/auth/me");
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
}
