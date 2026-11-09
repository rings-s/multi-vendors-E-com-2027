import { call, createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params }) => {
	const api = createApi(fetch, url.origin);
	const product = await must(
		api.GET('/api/v1/products/{product_id}', { params: { path: { product_id: params.id } } })
	);
	const more = call(
		api.GET('/api/v1/stores/{slug}/products', {
			params: { path: { slug: product.store.slug }, query: { page_size: 5 } }
		})
	).then((p) => p.items.filter((x) => x.id !== product.id).slice(0, 4));
	return { product, more };
};
