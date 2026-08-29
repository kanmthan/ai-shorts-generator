/**
 * Auth-related API helpers that sit on top of the shared `api` axios instance.
 *
 * Login and registration flow through `AuthContext` (token storage + profile
 * bootstrap live there). These wrappers cover the remaining Module 1 calls:
 * password-reset requests, profile updates and the Google OAuth redirect.
 */
import api from './api';
import type { User } from '../types';

export interface PasswordResetResponse {
  message: string;
}

export interface UpdateProfilePayload {
  full_name: string;
}

/** Base URL resolution mirrors `services/api.ts`. */
const OAUTH_BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api/v1`
  : '/api/v1';

/** POST /auth/password-reset — always resolves 200 to avoid account enumeration. */
export async function requestPasswordReset(
  email: string,
): Promise<PasswordResetResponse> {
  const { data } = await api.post<PasswordResetResponse>(
    '/auth/password-reset',
    { email },
  );
  return data;
}

/** PUT /auth/me — update the current user's profile. */
export async function updateProfile(
  payload: UpdateProfilePayload,
): Promise<User> {
  const { data } = await api.put<User>('/auth/me', payload);
  return data;
}

/**
 * Kick off the server-side Google OAuth flow by doing a full-page redirect to
 * `${VITE_API_URL}/api/v1/auth/google`. The backend sets `state` and redirects
 * back to the SPA once the exchange completes.
 */
export function startGoogleLogin(): void {
  window.location.assign(`${OAUTH_BASE_URL}/auth/google`);
}
