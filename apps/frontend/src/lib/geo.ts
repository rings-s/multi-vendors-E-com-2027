/**
 * "Detect my location" for address forms: browser geolocation → OpenStreetMap
 * Nominatim reverse geocoding → the fields of `AddressValue`.
 *
 * Nominatim is free and keyless (same provider as our map tiles) but its usage policy
 * allows at most ~1 request/second and no automated bulk use — fine for a button the
 * customer presses. Point `REVERSE_URL` at a self-hosted instance if traffic grows.
 */
import type { AddressValue } from '#lib/components/app/AddressFields.svelte';
import type { Locale } from '#lib/i18n/index.js';
import { REGIONS } from '#lib/saudi.js';

const REVERSE_URL = 'https://nominatim.openstreetmap.org/reverse';

export type DetectError = 'unsupported' | 'denied' | 'unavailable' | 'lookup' | 'outside';

export class DetectLocationError extends Error {
	constructor(readonly code: DetectError) {
		super(code);
	}
}

interface NominatimAddress {
	country_code?: string;
	'ISO3166-2-lvl4'?: string;
	state?: string;
	region?: string;
	province?: string;
	city?: string;
	town?: string;
	village?: string;
	hamlet?: string;
	municipality?: string;
	county?: string;
	suburb?: string;
	neighbourhood?: string;
	quarter?: string;
	city_district?: string;
	residential?: string;
	road?: string;
	pedestrian?: string;
	house_number?: string;
	postcode?: string;
}

/** Arabic-Indic and Persian digits → ASCII, so postal/building numbers validate. */
const asciiDigits = (s: string) => s.replace(/[٠-٩۰-۹]/g, (d) => String(d.charCodeAt(0) & 0xf));

/** "Riyadh Region" / "منطقة الرياض" / "Al-Qassim Province" → comparable stem. */
const stem = (s: string) =>
	s
		.toLowerCase()
		.replace(/\b(region|province|governorate)\b|منطقة|إمارة/g, '')
		.replace(/^(al|ar|ash|as|ad|an)[-\s]/, '')
		.replace(/[\s\-'’]/g, '')
		.replace(/^ال/, '');

function regionKey(a: NominatimAddress): string {
	const iso = a['ISO3166-2-lvl4'];
	const byIso = iso && REGIONS.find((r) => r.iso === iso);
	if (byIso) return byIso.key;
	const name = a.state ?? a.region ?? a.province;
	if (!name) return '';
	const s = stem(name);
	return REGIONS.find((r) => stem(r.en) === s || stem(r.ar) === s)?.key ?? '';
}

function currentPosition(): Promise<GeolocationPosition> {
	return new Promise((resolve, reject) => {
		if (typeof navigator === 'undefined' || !navigator.geolocation)
			return reject(new DetectLocationError('unsupported'));
		navigator.geolocation.getCurrentPosition(
			resolve,
			(e) =>
				reject(new DetectLocationError(e.code === e.PERMISSION_DENIED ? 'denied' : 'unavailable')),
			{ enableHighAccuracy: true, timeout: 15_000, maximumAge: 60_000 }
		);
	});
}

async function reverseGeocode(lat: number, lng: number, locale: Locale) {
	const q = new URLSearchParams({
		format: 'jsonv2',
		lat: String(lat),
		lon: String(lng),
		zoom: '18',
		addressdetails: '1',
		'accept-language': locale
	});
	try {
		const res = await fetch(`${REVERSE_URL}?${q}`, { signal: AbortSignal.timeout(10_000) });
		if (!res.ok) throw new Error(String(res.status));
		const body = (await res.json()) as { address?: NominatimAddress; error?: string };
		if (!body.address) throw new Error(body.error ?? 'no address');
		return body.address;
	} catch {
		throw new DetectLocationError('lookup');
	}
}

/**
 * Locate the device and return the address fields we could resolve. Fields the
 * geocoder didn't know are omitted, so callers can merge without wiping user input.
 * Throws `DetectLocationError`.
 */
export async function detectAddress(locale: Locale): Promise<Partial<AddressValue>> {
	const pos = await currentPosition();
	const a = await reverseGeocode(pos.coords.latitude, pos.coords.longitude, locale);
	if (a.country_code && a.country_code !== 'sa') throw new DetectLocationError('outside');

	const postal = asciiDigits(a.postcode ?? '').match(/\d{5}/)?.[0];
	const building = asciiDigits(a.house_number ?? '').trim();
	const out: Partial<AddressValue> = {
		region: regionKey(a),
		city: a.city ?? a.town ?? a.village ?? a.municipality ?? a.hamlet ?? a.county,
		district: a.suburb ?? a.neighbourhood ?? a.quarter ?? a.city_district ?? a.residential,
		street: a.road ?? a.pedestrian,
		building_number: building || undefined,
		postal_code: postal
	};
	const found = Object.fromEntries(
		Object.entries(out).filter(([, v]) => v)
	) as Partial<AddressValue>;
	// Keep the device position as the delivery pin (6 decimals ≈ 10 cm).
	found.latitude = Number(pos.coords.latitude.toFixed(6));
	found.longitude = Number(pos.coords.longitude.toFixed(6));
	return found;
}
