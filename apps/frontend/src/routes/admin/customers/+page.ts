import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:admin-users');
	const api = createApi(fetch, url.origin);
	const q = url.searchParams.get('q') ?? '';
	return {
		users: await must(
			api.GET('/api/v1/admin/customers', {
				params: { query: { q: q || undefined, page: pageParam(url), page_size: 25 } }
			})
		),
		q
	};
};
