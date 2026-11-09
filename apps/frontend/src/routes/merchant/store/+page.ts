import { call, createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:store');
	const api = createApi(fetch, url.origin);
	const [store, locations, categories] = await Promise.all([
		must(api.GET('/api/v1/merchant/store')),
		must(api.GET('/api/v1/merchant/store/locations')),
		call(api.GET('/api/v1/categories'))
	]);
	return { store, locations, categories };
};
