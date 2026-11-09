/**
 * Role helpers and server-side route guards. The backend is the authority on every
 * permission; these guards only decide which pages to render and where to send a
 * visitor who cannot use them.
 */
import { redirect, error } from '@sveltejs/kit';
import type { UserPublic } from '#lib/api/types.js';

export type Role = 'CUSTOMER' | 'MERCHANT' | 'ADMIN' | 'SUPER_ADMIN';

export function hasRole(user: UserPublic | null | undefined, ...roles: Role[]): boolean {
	return !!user && user.roles.some((r) => (roles as string[]).includes(r));
}

export const isAdmin = (u: UserPublic | null | undefined) => hasRole(u, 'ADMIN', 'SUPER_ADMIN');
export const isSuperAdmin = (u: UserPublic | null | undefined) => hasRole(u, 'SUPER_ADMIN');
export const isMerchant = (u: UserPublic | null | undefined) => hasRole(u, 'MERCHANT');
export const isCustomer = (u: UserPublic | null | undefined) => hasRole(u, 'CUSTOMER');

/** Where a user lands after signing in when no `next` is given. */
export function homeFor(user: UserPublic): string {
	if (isAdmin(user)) return '/admin';
	if (isMerchant(user)) return '/merchant';
	return '/account';
}

/** Only same-site relative paths are accepted as a post-login destination. */
export function safeNext(raw: string | null | undefined, fallback = '/'): string {
	return raw && raw.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/\\')
		? raw
		: fallback;
}

export function signInUrl(url: URL): string {
	return `/sign-in?next=${encodeURIComponent(url.pathname + url.search)}`;
}

/** Use in `+layout.server.ts` / `+page.server.ts`: signed-in user with one of `roles`. */
export function requireUser(locals: App.Locals, url: URL, ...roles: Role[]): UserPublic {
	const user = locals.user;
	if (!user) redirect(303, signInUrl(url));
	if (roles.length && !hasRole(user, ...roles))
		error(403, 'Forbidden', { code: 'permission_denied' });
	return user;
}
