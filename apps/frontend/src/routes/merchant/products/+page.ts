import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { CatalogStatus } from '#lib/api/types.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:products');
	const api = createApi(fetch, url.origin);
	const status = url.searchParams.get('status') ?? '';
	const q = url.searchParams.get('q') ?? '';
	const products = await must(
		api.GET('/api/v1/merchant/products', {
			params: {
				query: {
					status: (status || undefined) as CatalogStatus | undefined,
					q: q || undefined,
					page: pageParam(url),
					page_size: 20
				}
			}
		})
	);
	return { products, filters: { status, q } };
};
