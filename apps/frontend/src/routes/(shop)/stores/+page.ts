import { call, createApi } from '#lib/api/client.js';
import type { PageLoad } from './$types';

const SORTS = ['popular', 'newest', 'rating'] as const;
type Sort = (typeof SORTS)[number];

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const sp = url.searchParams;
	const sortParam = sp.get('sort');
	const filters = {
		q: sp.get('q') ?? '',
		category: sp.get('category') ?? '',
		city: sp.get('city') ?? '',
		min_rating: sp.get('min_rating') ?? '',
		sort: (SORTS as readonly string[]).includes(sortParam ?? '') ? (sortParam as Sort) : 'popular',
		page: Math.max(1, Number(sp.get('page')) || 1)
	};
	const [stores, categories] = await Promise.all([
		call(
			api.GET('/api/v1/stores', {
				params: {
					query: {
						q: filters.q || undefined,
						category: filters.category || undefined,
						city: filters.city || undefined,
						min_rating: filters.min_rating ? Number(filters.min_rating) : undefined,
						sort: filters.sort,
						page: filters.page,
						page_size: 12
					}
				}
			})
		),
		call(api.GET('/api/v1/categories'))
	]);
	return { stores, categories, filters };
};
