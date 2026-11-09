/**
 * Language and theme preferences. Both are stored in first-party cookies read by
 * `hooks.server.ts`, so the very first HTML response already has the right
 * `lang`, `dir` and `data-theme`. Signed-in users also get their language saved
 * on their profile (`PATCH /users/me`).
 */
import { invalidateAll } from '$app/navigation';
import { api } from '#lib/api/client.js';
import { dirOf, type Locale } from '#lib/i18n/index.js';

export type Theme = 'light' | 'dark' | 'system';
const YEAR = 60 * 60 * 24 * 365;

function setCookie(name: string, value: string) {
	const secure = location.protocol === 'https:' ? '; Secure' : '';
	document.cookie = `${name}=${value}; Path=/; Max-Age=${YEAR}; SameSite=Lax${secure}`;
}

export async function setLocale(locale: Locale, signedIn: boolean) {
	setCookie('lang', locale);
	document.documentElement.lang = locale;
	document.documentElement.dir = dirOf(locale);
	if (signedIn) {
		// Best effort: the cookie already applies the choice on this device.
		await api.PATCH('/api/v1/users/me', { body: { preferred_language: locale } }).catch(() => {});
	}
	await invalidateAll();
}

export function setTheme(theme: Theme) {
	setCookie('theme', theme);
	document.documentElement.dataset.theme = theme;
	void invalidateAll();
}
