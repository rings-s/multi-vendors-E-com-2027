import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params, depends }) => {
	depends('app:data-list');
	const api = createApi(fetch, url.origin);
	const model = params.model;
	// Filters are Django-style lookups taken verbatim from the URL (`?status=PAID&total__gte=100`).
	const query: Record<string, string | number> = Object.fromEntries(url.searchParams);
	query.page = pageParam(url);
	const [schema, rows] = await Promise.all([
		must(api.GET('/api/v1/admin/data/models/{model}', { params: { path: { model } } })),
		must(
			api.GET('/api/v1/admin/data/{model}', {
				params: { path: { model }, query: query as { page: number } }
			})
		)
	]);
	return { schema, rows };
};
