/**
 * Typed API client, generated from the API's OpenAPI document (src/api/schema.d.ts via
 * `npm run gen:api`), so the app and the API can't drift.
 */
import createClient, { type Middleware } from 'openapi-fetch';

import { apiBaseUrl } from './config';
import type { components, paths } from './schema';
import { useSession } from '@/state/session';

export type Schemas = components['schemas'];

export const auth: Middleware = {
  onRequest({ request }) {
    const token = useSession.getState().session?.token;
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  },
  onResponse({ response }) {
    // An expired or revoked session: sign out so the app returns to sign-in.
    if (response.status === 401 && useSession.getState().session) {
      useSession.getState().signOut();
    }
    return response;
  },
  onError({ error }) {
    // The request never got an answer: no connection, or the API isn't running.
    if (error instanceof Error && error.name === 'AbortError') return error;
    return new ApiError(OFFLINE, 0);
  },
};

export const OFFLINE = 'Curo couldn’t be reached. Check your connection.';

export const api = createClient<paths>({ baseUrl: apiBaseUrl() });
api.use(auth);

/** Error with the API's message ("detail") when it gave one. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/** Unwrap an openapi-fetch result: the data, or an ApiError with a readable message. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined && result.response.ok) return result.data;
  const detail = (result.error as { detail?: unknown } | undefined)?.detail;
  const message =
    typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? String((detail[0] as { msg?: string })?.msg ?? 'Something went wrong')
        : `Request failed (${result.response.status})`;
  throw new ApiError(message.replace(/^Value error, /, ''), result.response.status);
}
