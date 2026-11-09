import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params }) => {
	const api = createApi(fetch, url.origin);
	const order = await must(
		api.GET('/api/v1/orders/{order_id}', { params: { path: { order_id: params.orderId } } })
	);
	return { order };
};
