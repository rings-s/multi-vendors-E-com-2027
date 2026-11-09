import { call, createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params }) => {
	const api = createApi(fetch, url.origin);
	const [product, categories] = await Promise.all([
		must(
			api.GET('/api/v1/merchant/products/{product_id}', {
				params: { path: { product_id: params.id } }
			})
		),
		call(api.GET('/api/v1/categories'))
	]);
	return { product, categories };
};
