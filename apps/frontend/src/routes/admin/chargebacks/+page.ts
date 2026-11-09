import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:chargebacks');
	const api = createApi(fetch, url.origin);
	return {
		chargebacks: await must(
			api.GET('/api/v1/admin/chargebacks', {
				params: { query: { page: pageParam(url), page_size: 25 } }
			})
		)
	};
};
