/**
 * Server hooks.
 *
 * 1. Same-origin backend proxy. `/api/v1/*` and `/media/*` are forwarded to the FastAPI
 *    backend (`API_URL`). The browser never talks to the backend directly, so the
 *    backend's HTTP-only auth cookies are first-party, CORS is not needed, and no
 *    backend address or secret is exposed to the client.
 * 2. Session resume. Access tokens live 15 minutes; the refresh cookie is scoped by the
 *    backend to `/api/v1/auth`, so a page request cannot see it. When a page is requested
 *    without an access token but with the `has_session` hint, the browser is redirected
 *    once through `/api/v1/auth/_bff/resume` (which does receive the refresh cookie),
 *    the session is rotated server-side, and the browser comes back to the page.
 * 3. Locale and theme resolution, written into `<html lang dir data-theme>`.
 */
import type { RequestEvent } from '@sveltejs/kit';
import type { Handle } from '@sveltejs/kit/hooks';
import { redirect } from '@sveltejs/kit';
import { API_URL } from '$app/env/private';
import type { UserPublic } from '#lib/api/types.js';
import { resolveLocale, dirOf, type Locale } from '#lib/i18n/index.js';

const SESSION_HINT = 'has_session';
const RESUME_GUARD = 'resume_attempt';
const RESUME_PATH = '/api/v1/auth/_bff/resume';
const HINT_MAX_AGE = 60 * 60 * 24 * 30; // matches the backend refresh-token TTL
const PROXIED = /^\/(api\/v1|media)(\/|$)/;
const SESSION_START = /^\/api\/v1\/(auth\/(login|register|refresh)|merchants\/register)$/;
const SESSION_END = /^\/api\/v1\/auth\/(logout|logout-all)$/;
const HOP_BY_HOP = [
	'host',
	'connection',
	'keep-alive',
	'content-length',
	'transfer-encoding',
	'accept-encoding',
	'upgrade'
];

function hintCookie(event: RequestEvent, on: boolean): string {
	const secure = event.url.protocol === 'https:' ? '; Secure' : '';
	return on
		? `${SESSION_HINT}=1; Path=/; Max-Age=${HINT_MAX_AGE}; SameSite=Lax${secure}`
		: `${SESSION_HINT}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
}

function forwardHeaders(event: RequestEvent, locale: Locale): Headers {
	const headers = new Headers(event.request.headers);
	for (const h of HOP_BY_HOP) headers.delete(h);
	headers.set('x-forwarded-for', event.getClientAddress());
	headers.set('x-forwarded-proto', event.url.protocol.replace(':', ''));
	headers.set('x-forwarded-host', event.url.host);
	headers.set('accept-language', locale);
	return headers;
}

function cleanResponse(res: Response): Response {
	const headers = new Headers(res.headers);
	// `fetch` already decoded the body; the original framing headers no longer apply.
	headers.delete('content-encoding');
	headers.delete('content-length');
	headers.delete('transfer-encoding');
	return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
}

async function proxy(event: RequestEvent, locale: Locale): Promise<Response> {
	const { request, url } = event;
	const target = `${API_URL}${url.pathname}${url.search}`;
	const hasBody = !['GET', 'HEAD'].includes(request.method);
	let upstream: Response;
	try {
		upstream = await fetch(target, {
			method: request.method,
			headers: forwardHeaders(event, locale),
			body: hasBody ? request.body : undefined,
			redirect: 'manual',
			// @ts-expect-error -- Node's fetch requires `duplex` when streaming a request body.
			duplex: hasBody ? 'half' : undefined
		});
	} catch {
		return Response.json(
			{
				error: {
					code: 'backend_unavailable',
					message: 'The service is unavailable.',
					details: null
				}
			},
			{ status: 503 }
		);
	}
	const response = cleanResponse(upstream);
	if (SESSION_START.test(url.pathname)) {
		if (upstream.ok) response.headers.append('set-cookie', hintCookie(event, true));
		else if (url.pathname.endsWith('/refresh') && upstream.status === 401)
			response.headers.append('set-cookie', hintCookie(event, false));
	} else if (SESSION_END.test(url.pathname) && (upstream.ok || upstream.status === 401)) {
		response.headers.append('set-cookie', hintCookie(event, false));
	}
	return response;
}

function safeNext(raw: string | null): string {
	return raw && raw.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/\\') ? raw : '/';
}

/** GET /api/v1/auth/_bff/resume?next=/path — rotate the session server-side, then go back. */
async function resume(event: RequestEvent, locale: Locale): Promise<Response> {
	const next = safeNext(event.url.searchParams.get('next'));
	const headers = forwardHeaders(event, locale);
	headers.delete('content-type');
	const out = new Headers({ location: next, 'cache-control': 'no-store' });
	out.append('set-cookie', `${RESUME_GUARD}=1; Path=/; Max-Age=15; SameSite=Lax`);

	if (event.cookies.get('refresh_token')) {
		try {
			// The refresh endpoint requires the double-submit CSRF pair. This is a
			// server-to-server call, so mint one if the browser no longer has it.
			let csrf = event.cookies.get('csrf_token');
			if (!csrf) {
				const r = await fetch(`${API_URL}/api/v1/auth/csrf`);
				csrf = ((await r.json()) as { csrf_token: string }).csrf_token;
				const cookie = headers.get('cookie') ?? '';
				headers.set('cookie', `${cookie}${cookie ? '; ' : ''}csrf_token=${csrf}`);
			}
			headers.set('x-csrf-token', csrf);
			const res = await fetch(`${API_URL}/api/v1/auth/refresh`, { method: 'POST', headers });
			if (res.ok) {
				for (const c of res.headers.getSetCookie()) out.append('set-cookie', c);
				out.append('set-cookie', hintCookie(event, true));
				return new Response(null, { status: 303, headers: out });
			}
		} catch {
			// Fall through: continue as a signed-out visitor.
		}
	}
	out.append('set-cookie', hintCookie(event, false));
	return new Response(null, { status: 303, headers: out });
}

async function currentUser(event: RequestEvent, locale: Locale): Promise<UserPublic | null> {
	if (!event.cookies.get('access_token')) return null;
	try {
		const res = await fetch(`${API_URL}/api/v1/auth/me`, {
			headers: { cookie: event.request.headers.get('cookie') ?? '', 'accept-language': locale }
		});
		return res.ok ? ((await res.json()) as UserPublic) : null;
	} catch {
		return null;
	}
}

function isDocumentRequest(event: RequestEvent): boolean {
	return (
		event.request.method === 'GET' &&
		(event.request.headers.get('accept') ?? '').includes('text/html') &&
		!event.isDataRequest
	);
}

export const handle: Handle = async ({ event, resolve }) => {
	const cookieLocale = event.cookies.get('lang');
	let locale = resolveLocale(cookieLocale, event.request.headers.get('accept-language'));

	if (event.url.pathname === RESUME_PATH && event.request.method === 'GET') {
		return resume(event, locale);
	}
	if (PROXIED.test(event.url.pathname)) {
		return proxy(event, locale);
	}

	const user = await currentUser(event, locale);
	if (
		!user &&
		event.cookies.get(SESSION_HINT) &&
		!event.cookies.get(RESUME_GUARD) &&
		isDocumentRequest(event)
	) {
		redirect(
			303,
			`${RESUME_PATH}?next=${encodeURIComponent(event.url.pathname + event.url.search)}`
		);
	}
	if (
		user &&
		!cookieLocale &&
		(user.preferred_language === 'ar' || user.preferred_language === 'en')
	) {
		locale = user.preferred_language;
	}

	const themeCookie = event.cookies.get('theme');
	const theme = themeCookie === 'light' || themeCookie === 'dark' ? themeCookie : 'system';

	event.locals.user = user;
	event.locals.locale = locale;
	event.locals.theme = theme;

	const response = await resolve(event, {
		transformPageChunk: ({ html }) =>
			html.replace('%lang%', locale).replace('%dir%', dirOf(locale)).replace('%theme%', theme)
	});
	if ((response.headers.get('content-type') ?? '').includes('text/html')) {
		response.headers.set('x-content-type-options', 'nosniff');
		response.headers.set('referrer-policy', 'strict-origin-when-cross-origin');
		response.headers.set('x-frame-options', 'DENY');
	}
	return response;
};
