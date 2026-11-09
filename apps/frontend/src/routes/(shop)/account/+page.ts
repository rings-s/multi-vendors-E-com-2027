import { call, createApi } from '#lib/api/client.js';
import { isCustomer } from '#lib/auth.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, parent }) => {
	const { user } = await parent();
	if (!isCustomer(user)) return { orders: null };
	const api = createApi(fetch, url.origin);
	return { orders: await call(api.GET('/api/v1/orders', { params: { query: { page_size: 5 } } })) };
};
