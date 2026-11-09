import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:delivery');
	const api = createApi(fetch, url.origin);
	const [settings, zones] = await Promise.all([
		must(api.GET('/api/v1/merchant/delivery/settings')),
		must(api.GET('/api/v1/merchant/delivery/zones'))
	]);
	return { settings, zones };
};
