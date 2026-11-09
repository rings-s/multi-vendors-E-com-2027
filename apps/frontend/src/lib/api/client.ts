/**
 * Typed API client for the FastAPI backend.
 *
 * - Request and response types come from the generated OpenAPI schema (`schema.d.ts`).
 * - All calls go to the same origin (`/api/v1/*`); the SvelteKit server proxies them
 *   to the backend (`hooks.server.ts`), so authentication cookies are first-party.
 * - In the browser, state-changing requests carry the double-submit CSRF header the
 *   backend requires (`app/core/csrf.py`).
 * - In the browser, a 401 caused by an expired access token triggers one shared
 *   refresh (`POST /auth/refresh`) and the request is retried once. Refreshes are
 *   single-flight because the backend revokes the whole session if a refresh token
 *   is reused.
 *
 * In `load` functions pass the event's `fetch` and `url.origin` so SSR requests
 * forward the user's cookies: `createApi(fetch, url.origin)`.
 */
import createClient from 'openapi-fetch';
import { browser } from '$app/env';
import type { paths } from './schema';
import { toApiError } from './errors';

export type Api = ReturnType<typeof createClient<paths>>;

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);
/** Endpoints that must never trigger a silent refresh-and-retry. */
const NO_RETRY = /\/api\/v1\/auth\/(login|register|refresh|logout|logout-all)$/;

export const CSRF_COOKIE = 'csrf_token';
export const SESSION_HINT_COOKIE = 'has_session';

function readCookie(name: string): string | null {
	if (!browser) return null;
	for (const part of document.cookie.split(';')) {
		const [k, ...v] = part.trim().split('=');
		if (k === name) return decodeURIComponent(v.join('='));
	}
	return null;
}

export async function ensureCsrfToken(): Promise<string | null> {
	let token = readCookie(CSRF_COOKIE);
	if (!token) {
		const res = await fetch('/api/v1/auth/csrf', { credentials: 'same-origin' });
		if (res.ok) token = ((await res.json()) as { csrf_token: string }).csrf_token;
	}
	return token;
}

let refreshing: Promise<boolean> | null = null;
let onSessionExpired: (() => void) | null = null;

/** Registered by the root layout: called when the session can no longer be refreshed. */
export function setSessionExpiredHandler(handler: () => void) {
	onSessionExpired = handler;
}

/** Refresh the access token once, even when many requests fail at the same time. */
export function refreshSession(): Promise<boolean> {
	refreshing ??= (async () => {
		try {
			const csrf = await ensureCsrfToken();
			const res = await fetch('/api/v1/auth/refresh', {
				method: 'POST',
				credentials: 'same-origin',
				headers: csrf ? { 'x-csrf-token': csrf } : {}
			});
			return res.ok;
		} catch {
			return false;
		} finally {
			queueMicrotask(() => (refreshing = null));
		}
	})();
	return refreshing;
}

function browserFetch(base: typeof fetch) {
	return async (request: Request): Promise<Response> => {
		if (!SAFE_METHODS.has(request.method) && !request.headers.has('x-csrf-token')) {
			const csrf = await ensureCsrfToken();
			if (csrf) request.headers.set('x-csrf-token', csrf);
		}
		const retry = NO_RETRY.test(new URL(request.url).pathname) ? null : request.clone();
		const response = await base(request);
		if (response.status !== 401 || !retry || !readCookie(SESSION_HINT_COOKIE)) return response;

		const code = await response
			.clone()
			.json()
			.then((b: { error?: { code?: string } }) => b?.error?.code)
			.catch(() => undefined);
		if (code !== 'not_authenticated' && code !== 'invalid_token') return response;

		if (await refreshSession()) {
			const csrf = readCookie(CSRF_COOKIE);
			if (csrf && !SAFE_METHODS.has(retry.method)) retry.headers.set('x-csrf-token', csrf);
			return base(retry);
		}
		onSessionExpired?.();
		return response;
	};
}

export function createApi(fetchFn: typeof fetch = fetch, origin?: string): Api {
	const baseUrl = origin ?? (browser ? location.origin : '');
	return createClient<paths>({
		baseUrl,
		fetch: browser ? browserFetch(fetchFn) : (request: Request) => fetchFn(request),
		credentials: 'same-origin'
	});
}

/** The shared browser client. Use `createApi(fetch, url.origin)` inside `load`. */
export const api: Api = createApi();

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Unwrap an openapi-fetch result: return `data` or throw an `ApiError`. */
export async function call<T>(promise: Promise<Result<T>>): Promise<T> {
	const { data, error, response } = await promise;
	if (!response.ok) throw toApiError(response.status, error);
	return data as T;
}

/** Generate an idempotency key for `POST /checkout` (`Idempotency-Key`, 8–100 chars). */
export function idempotencyKey(): string {
	return crypto.randomUUID();
}

export type UploadPurpose = 'product' | 'service' | 'store' | 'category' | 'homepage';

/** Upload an image (multipart) and return its public URL. Browser only. */
export async function uploadImage(file: File, purpose: UploadPurpose): Promise<string> {
	const body = new FormData();
	body.append('file', file);
	const send = async () => {
		const csrf = await ensureCsrfToken();
		return fetch(`/api/v1/uploads/images?purpose=${purpose}`, {
			method: 'POST',
			body,
			credentials: 'same-origin',
			headers: csrf ? { 'x-csrf-token': csrf } : {}
		});
	};
	let res = await send();
	if (res.status === 401 && (await refreshSession())) res = await send();
	const payload = await res.json().catch(() => null);
	if (!res.ok) throw toApiError(res.status, payload);
	return (payload as { url: string }).url;
}

/**
 * Where to send the payer. Mock-provider hosted pages are served by the backend under
 * `/api/v1/mock-provider/*`; they are opened through the same-origin proxy so the
 * flow works regardless of the backend's public URL. Real provider URLs are returned
 * unchanged.
 */
export function paymentRedirectUrl(transactionUrl: string): string {
	try {
		const u = new URL(transactionUrl, browser ? location.origin : 'http://localhost');
		if (u.pathname.startsWith('/api/v1/mock-provider/')) return u.pathname + u.search;
		return u.toString();
	} catch {
		return transactionUrl;
	}
}
