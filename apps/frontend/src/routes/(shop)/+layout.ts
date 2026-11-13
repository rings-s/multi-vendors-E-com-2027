import { call, createApi } from '#lib/api/client.js';
import type { Category } from '#lib/api/types.js';
import type { LayoutLoad } from './$types';

/** Top-level categories for the storefront tab bar. The shop still works if they fail to load. */
export const load: LayoutLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	let categories: Category[] = [];
	try {
		categories = await call(api.GET('/api/v1/categories'));
	} catch {
		// Navigation falls back to the fixed links.
	}
	return { navCategories: categories.filter((c) => c.is_active && !c.parent_id) };
};
