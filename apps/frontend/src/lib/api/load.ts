/**
 * Helpers for `load` functions: map backend errors onto SvelteKit's error pages.
 */
import { error } from '@sveltejs/kit';
import { call } from './client';
import { isApiError } from './errors';

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Like `call`, but a missing resource renders the 404 page and a forbidden one the 403 page. */
export async function must<T>(promise: Promise<Result<T>>): Promise<T> {
	try {
		return await call(promise);
	} catch (e) {
		if (isApiError(e)) {
			if (e.status === 404 || e.status === 422) error(404, 'Not found', { code: 'not_found' });
			if (e.status === 403) error(403, 'Forbidden', { code: e.code });
			if (e.status === 401) error(401, 'Unauthorized', { code: e.code });
		}
		throw e;
	}
}

/** Read `?page=` as a positive integer. */
export function pageParam(url: URL, name = 'page'): number {
	return Math.max(1, Math.floor(Number(url.searchParams.get(name))) || 1);
}
