import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { CatalogStatus } from '#lib/api/types.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:moderation');
	const api = createApi(fetch, url.origin);
	const tab = url.searchParams.get('tab') === 'services' ? 'services' : 'products';
	const status = url.searchParams.get('status') ?? '';
	const q = url.searchParams.get('q') ?? '';
	const page = pageParam(url);
	if (tab === 'services') {
		// Services have no admin listing endpoint; moderate from the public catalogue.
		const services = await must(
			api.GET('/api/v1/services', { params: { query: { q: q || undefined, page, page_size: 25 } } })
		);
		return { tab, products: null, services, filters: { status, q } };
	}
	const products = await must(
		api.GET('/api/v1/admin/products', {
			params: {
				query: {
					status: (status || undefined) as CatalogStatus | undefined,
					q: q || undefined,
					page,
					page_size: 25
				}
			}
		})
	);
	return { tab, products, services: null, filters: { status, q } };
};
