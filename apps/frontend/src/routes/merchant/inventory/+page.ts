import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:inventory');
	const api = createApi(fetch, url.origin);
	return { inventory: await must(api.GET('/api/v1/merchant/inventory')) };
};
