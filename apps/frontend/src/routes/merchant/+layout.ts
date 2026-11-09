import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async ({ fetch, url, depends }) => {
	depends('app:merchant');
	const api = createApi(fetch, url.origin);
	return { merchant: await must(api.GET('/api/v1/merchants/me')) };
};
