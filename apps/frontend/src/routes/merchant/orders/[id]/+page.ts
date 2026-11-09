import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params, depends }) => {
	depends('app:merchant-order');
	const api = createApi(fetch, url.origin);
	return {
		order: await must(
			api.GET('/api/v1/merchant/orders/{mo_id}', { params: { path: { mo_id: params.id } } })
		)
	};
};
