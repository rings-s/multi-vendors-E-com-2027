/**
 * Delivery display helpers. Every amount and status comes from the backend; these
 * only format what the API returns.
 */
import { intlTag, type Locale } from '#lib/i18n/index.js';

/** A delivery window such as "2–6 hours" or "1–3 days", in the active language. */
export function etaRange(minMinutes: number, maxMinutes: number, locale: Locale): string {
	const tag = intlTag(locale);
	const [unit, size] =
		maxMinutes < 90
			? (['minute', 1] as const)
			: maxMinutes < 2160
				? (['hour', 60] as const)
				: (['day', 1440] as const);
	const lo = Math.max(0, Math.round(minMinutes / size));
	const hi = Math.max(lo, Math.round(maxMinutes / size));
	const withUnit = new Intl.NumberFormat(tag, { style: 'unit', unit, unitDisplay: 'long' });
	if (lo === hi || lo === 0) return withUnit.format(hi);
	return `${new Intl.NumberFormat(tag).format(lo)}–${withUnit.format(hi)}`;
}

/** A maps link for a WGS84 pin (opens the device's map app on phones). */
export function mapsLink(lat: number, lng: number): string {
	return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
}

/** "Riyadh, الرياض" → ["Riyadh", "الرياض"] (also accepts Arabic commas and new lines). */
export function splitPlaces(text: string): string[] {
	return text
		.split(/[,،\n]/)
		.map((s) => s.trim())
		.filter(Boolean);
}

/** One-line address. Pass `fmt.list` so parts are bidi-isolated and joined per locale. */
export function formatAddress(
	a: Record<string, unknown> | null | undefined,
	regionName: (key: string) => string,
	list: (parts: unknown[]) => string
): string {
	if (!a) return '';
	return list([
		a.street,
		a.building_number,
		a.district,
		a.city,
		a.region ? regionName(String(a.region)) : '',
		a.postal_code
	]);
}
