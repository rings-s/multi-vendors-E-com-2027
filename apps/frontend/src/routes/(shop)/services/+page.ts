import { call, createApi } from '#lib/api/client.js';
import { pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

const SORTS = ['newest', 'price_asc', 'price_desc', 'popular'] as const;
type Sort = (typeof SORTS)[number];

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const sp = url.searchParams;
	const filters = {
		q: sp.get('q') ?? '',
		category: sp.get('category') ?? '',
		city: sp.get('city') ?? '',
		sort: ((SORTS as readonly string[]).includes(sp.get('sort') ?? '')
			? sp.get('sort')
			: 'newest') as Sort
	};
	const [services, categories] = await Promise.all([
		call(
			api.GET('/api/v1/services', {
				params: {
					query: {
						q: filters.q || undefined,
						category: filters.category || undefined,
						city: filters.city || undefined,
						sort: filters.sort,
						page: pageParam(url),
						page_size: 20
					}
				}
			})
		),
		call(api.GET('/api/v1/categories'))
	]);
	return { services, categories, filters };
};
