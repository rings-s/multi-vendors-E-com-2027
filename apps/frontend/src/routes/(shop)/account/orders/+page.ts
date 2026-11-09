import { error } from '@sveltejs/kit';
import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import { isCustomer } from '#lib/auth.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, parent }) => {
	const { user } = await parent();
	if (!isCustomer(user)) error(403, 'Forbidden', { code: 'permission_denied' });
	const api = createApi(fetch, url.origin);
	return {
		orders: await must(
			api.GET('/api/v1/orders', { params: { query: { page: pageParam(url), page_size: 15 } } })
		)
	};
};
