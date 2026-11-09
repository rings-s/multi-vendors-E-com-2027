import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:tickets');
	const api = createApi(fetch, url.origin);
	return {
		tickets: await must(
			api.GET('/api/v1/support/tickets', {
				params: { query: { page: pageParam(url), page_size: 10 } }
			})
		)
	};
};
