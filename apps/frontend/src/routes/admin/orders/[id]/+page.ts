import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params, depends }) => {
	depends('app:admin-order');
	const api = createApi(fetch, url.origin);
	return {
		detail: await must(
			api.GET('/api/v1/admin/orders/{order_id}', { params: { path: { order_id: params.id } } })
		)
	};
};
