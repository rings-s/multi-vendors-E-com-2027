/**
 * Bidirectional-text helpers.
 *
 * User and backend data (store names, product titles, addresses…) is often Latin while
 * the page is Arabic (RTL), or the reverse. Without isolation the browser lays such text
 * out in the paragraph's direction, so neutral characters jump to the wrong side:
 * "Najd Oud Trading Est." renders as ".Najd Oud Trading Est".
 *
 * In markup, wrap the value in `<bdi>`. Where only a plain string is possible (joined
 * lists, `<option>`, `title`, `aria-label`), use `isolate()`: it wraps the text in
 * FIRST STRONG ISOLATE … POP DIRECTIONAL ISOLATE, the plain-text equivalent of `<bdi>`.
 */
import type { Locale } from './index';

const FSI = '⁨';
const PDI = '⁩';

export function isolate(text: string | null | undefined): string {
	return text ? `${FSI}${text}${PDI}` : '';
}

/** Join parts (e.g. address lines) with the locale's comma, each part isolated. */
export function joinIsolated(parts: unknown[], locale: Locale): string {
	return parts
		.filter((p) => p !== null && p !== undefined && p !== '')
		.map((p) => isolate(String(p)))
		.join(locale === 'ar' ? '، ' : ', ');
}
