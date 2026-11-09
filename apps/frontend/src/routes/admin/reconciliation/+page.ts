import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:reconciliation');
	const api = createApi(fetch, url.origin);
	return {
		runs: await must(
			api.GET('/api/v1/admin/reconciliation', {
				params: { query: { page: pageParam(url), page_size: 20 } }
			})
		)
	};
};
