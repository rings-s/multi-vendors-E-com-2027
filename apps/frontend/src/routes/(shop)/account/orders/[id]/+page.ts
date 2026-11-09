import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params, depends }) => {
	depends('app:order');
	const api = createApi(fetch, url.origin);
	const path = { path: { order_id: params.id } };
	const [order, history] = await Promise.all([
		must(api.GET('/api/v1/orders/{order_id}', { params: path })),
		must(api.GET('/api/v1/orders/{order_id}/history', { params: path }))
	]);
	return { order, history };
};
