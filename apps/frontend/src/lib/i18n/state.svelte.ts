/**
 * Reactive i18n accessors for components.
 *
 * The locale is read from `page.data.locale` (set by the root layout from the server
 * hook), so it is request-scoped during SSR and never leaks between users.
 *
 *   import { m, fmt, locale } from '#lib/i18n/state.svelte.js';
 *   <h1>{m().nav.stores}</h1>  <span>{fmt.money(product.price)}</span>
 */
import { page } from '$app/state';
import { ApiError } from '#lib/api/errors.js';
import {
	formatDate,
	formatMoney,
	formatNumber,
	formatPercent,
	formatPhone,
	formatRelative
} from '#lib/format.js';
import { regionName } from '#lib/saudi.js';
import { joinIsolated } from './bidi';
import { DEFAULT_LOCALE, dirOf, isLocale, type Locale } from './index';
import ar from './messages/ar';
import en, { type Messages } from './messages/en';

const catalogs: Record<Locale, Messages> = { ar, en };

export function locale(): Locale {
	const l = page.data?.locale;
	return isLocale(l) ? l : DEFAULT_LOCALE;
}

export function dir(): 'rtl' | 'ltr' {
	return dirOf(locale());
}

export function m(): Messages {
	return catalogs[locale()];
}

/** Localised label for a backend enum value (order, payment, merchant… statuses). */
export function statusLabel(value: string | null | undefined): string {
	if (!value) return '—';
	const map = m().status as Record<string, string>;
	return map[value] ?? value.replace(/_/g, ' ').toLowerCase();
}

/** Bilingual backend fields: pick `name_ar` / `name_en` (or `title_*`, `quote_*`). */
export function pick<T extends object>(obj: T, field: string): string {
	const rec = obj as Record<string, unknown>;
	const primary = rec[`${field}_${locale()}`];
	const fallback = rec[`${field}_${locale() === 'ar' ? 'en' : 'ar'}`];
	return (typeof primary === 'string' && primary) || (typeof fallback === 'string' ? fallback : '');
}

/** Translate an API error by its stable `code`; fall back to a generic message. */
export function errorMessage(e: unknown): string {
	const t = m().errors;
	if (e instanceof ApiError) {
		const codes = t.codes as Record<string, string>;
		if (codes[e.code]) return codes[e.code];
		if (e.status === 0) return t.network;
		return t.generic;
	}
	if (e instanceof TypeError) return t.network;
	return t.generic;
}

export const fmt = {
	money: (halalas: number | null | undefined) => formatMoney(halalas, locale()),
	number: (n: number | null | undefined) => formatNumber(n, locale()),
	percent: (rate: number | string | null | undefined) => formatPercent(rate, locale()),
	date: (iso: string | null | undefined) => formatDate(iso, locale(), 'date'),
	datetime: (iso: string | null | undefined) => formatDate(iso, locale(), 'datetime'),
	shortDate: (iso: string | null | undefined) => formatDate(iso, locale(), 'short'),
	relative: (iso: string) => formatRelative(iso, locale()),
	phone: formatPhone,
	region: (key: string | null | undefined) => regionName(key, locale()),
	/** Locale-aware comma list with each part bidi-isolated (addresses, "city, region"). */
	list: (parts: unknown[]) => joinIsolated(parts, locale())
};
