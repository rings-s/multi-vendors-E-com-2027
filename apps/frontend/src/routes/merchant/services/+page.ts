import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:services');
	const api = createApi(fetch, url.origin);
	return {
		services: await must(
			api.GET('/api/v1/merchant/services', {
				params: { query: { page: pageParam(url), page_size: 20 } }
			})
		)
	};
};
