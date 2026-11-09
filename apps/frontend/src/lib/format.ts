/**
 * Display formatting. Amounts are integer halalas (1 SAR = 100 halalas) exactly as
 * the backend sends them; the frontend only formats money, it never computes
 * financial allocations.
 */
import { intlTag, type Locale } from '#lib/i18n/index.js';

const moneyCache = new Map<string, Intl.NumberFormat>();

export function formatMoney(halalas: number | null | undefined, locale: Locale): string {
	const key = locale;
	let f = moneyCache.get(key);
	if (!f) {
		f = new Intl.NumberFormat(intlTag(locale), {
			style: 'currency',
			currency: 'SAR',
			minimumFractionDigits: 2,
			maximumFractionDigits: 2
		});
		moneyCache.set(key, f);
	}
	return f.format((halalas ?? 0) / 100);
}

/** Convert a SAR amount typed by a user ("12.5") to integer halalas, or null if invalid. */
export function sarToHalalas(input: string | number): number | null {
	const text = String(input)
		.trim()
		.replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));
	if (!/^\d+(\.\d{1,2})?$/.test(text)) return null;
	const [whole, frac = ''] = text.split('.');
	return Number(whole) * 100 + Number(frac.padEnd(2, '0'));
}

/** Integer halalas to an editable SAR string ("12.50"). */
export function halalasToSar(halalas: number | null | undefined): string {
	if (halalas == null) return '';
	const sign = halalas < 0 ? '-' : '';
	const abs = Math.abs(halalas);
	return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

export function formatNumber(n: number | null | undefined, locale: Locale): string {
	return new Intl.NumberFormat(intlTag(locale)).format(n ?? 0);
}

export function formatPercent(rate: number | string | null | undefined, locale: Locale): string {
	if (rate == null || rate === '') return '—';
	return (
		new Intl.NumberFormat(intlTag(locale), { maximumFractionDigits: 2 }).format(Number(rate)) + '%'
	);
}

export function formatDate(
	iso: string | null | undefined,
	locale: Locale,
	style: 'date' | 'datetime' | 'short' = 'date'
): string {
	if (!iso) return '—';
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return '—';
	const opts: Intl.DateTimeFormatOptions =
		style === 'datetime'
			? { dateStyle: 'medium', timeStyle: 'short' }
			: style === 'short'
				? { month: 'short', day: 'numeric' }
				: { dateStyle: 'medium' };
	return new Intl.DateTimeFormat(intlTag(locale), { timeZone: 'Asia/Riyadh', ...opts }).format(d);
}

export function formatRelative(iso: string, locale: Locale, now = Date.now()): string {
	const diff = (new Date(iso).getTime() - now) / 1000;
	const rtf = new Intl.RelativeTimeFormat(intlTag(locale), { numeric: 'auto' });
	const abs = Math.abs(diff);
	if (abs < 60) return rtf.format(Math.round(diff), 'second');
	if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute');
	if (abs < 86400) return rtf.format(Math.round(diff / 3600), 'hour');
	if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), 'day');
	return formatDate(iso, locale);
}

/** "+966512345678" → "+966 51 234 5678" (display only; the backend normalises input). */
export function formatPhone(phone: string | null | undefined): string {
	if (!phone) return '—';
	const m = /^\+966(5\d)(\d{3})(\d{4})$/.exec(phone);
	return m ? `+966 ${m[1]} ${m[2]} ${m[3]}` : phone;
}

/** Client-side mirror of the backend's Saudi mobile normaliser, for instant feedback only. */
export function normalizeSaudiMobile(value: string): string | null {
	const cleaned = value.replace(/[\s\-()]/g, '');
	const m = /^(?:\+?966|0)?(5\d{8})$/.exec(cleaned);
	return m ? `+966${m[1]}` : null;
}

export function initials(name: string): string {
	const parts = name.trim().split(/\s+/).filter(Boolean);
	return (parts[0]?.[0] ?? '') + (parts.length > 1 ? (parts[parts.length - 1][0] ?? '') : '');
}
