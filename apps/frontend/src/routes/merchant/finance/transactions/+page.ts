import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	return {
		transactions: await must(
			api.GET('/api/v1/merchant/transactions', {
				params: { query: { page: pageParam(url), page_size: 30 } }
			})
		)
	};
};
