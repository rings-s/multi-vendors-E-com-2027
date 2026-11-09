/**
 * Locale primitives shared by server hooks and components. Arabic is the default
 * (as in the backend, `app/core/i18n.py`); English is fully supported.
 */
export type Locale = 'ar' | 'en';
export const LOCALES: readonly Locale[] = ['ar', 'en'];
export const DEFAULT_LOCALE: Locale = 'ar';

export function isLocale(value: unknown): value is Locale {
	return value === 'ar' || value === 'en';
}

export function dirOf(locale: Locale): 'rtl' | 'ltr' {
	return locale === 'ar' ? 'rtl' : 'ltr';
}

/** Cookie preference first, then the browser's Accept-Language, then Arabic. */
export function resolveLocale(cookie: string | undefined, acceptLanguage: string | null): Locale {
	if (isLocale(cookie)) return cookie;
	for (const part of (acceptLanguage ?? '').split(',')) {
		const tag = part.trim().slice(0, 2).toLowerCase();
		if (isLocale(tag)) return tag;
	}
	return DEFAULT_LOCALE;
}

/**
 * Intl locale tags. Gregorian calendar and Latin digits are used in both languages
 * so that prices, order numbers and financial figures read identically everywhere.
 */
export function intlTag(locale: Locale): string {
	return locale === 'ar' ? 'ar-SA-u-ca-gregory-nu-latn' : 'en-SA';
}
