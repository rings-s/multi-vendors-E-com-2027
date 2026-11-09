import { call, createApi } from '#lib/api/client.js';
import { pageParam } from '#lib/api/load.js';
import { sarToHalalas } from '#lib/format.js';
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
		min_price: sp.get('min_price') ?? '',
		max_price: sp.get('max_price') ?? '',
		sort: ((SORTS as readonly string[]).includes(sp.get('sort') ?? '')
			? sp.get('sort')
			: 'newest') as Sort
	};
	const min = filters.min_price ? sarToHalalas(filters.min_price) : null;
	const max = filters.max_price ? sarToHalalas(filters.max_price) : null;
	const [products, categories] = await Promise.all([
		call(
			api.GET('/api/v1/products', {
				params: {
					query: {
						q: filters.q || undefined,
						category: filters.category || undefined,
						city: filters.city || undefined,
						min_price: min ?? undefined,
						max_price: max ?? undefined,
						sort: filters.sort,
						page: pageParam(url),
						page_size: 24
					}
				}
			})
		),
		call(api.GET('/api/v1/categories'))
	]);
	return { products, categories, filters };
};
