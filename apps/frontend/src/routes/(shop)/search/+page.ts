import { call, createApi } from '#lib/api/client.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const q = (url.searchParams.get('q') ?? '').trim();
	if (!q) return { q, results: null };
	const api = createApi(fetch, url.origin);
	const [stores, products, services] = await Promise.all([
		call(api.GET('/api/v1/stores', { params: { query: { q, page_size: 6 } } })),
		call(api.GET('/api/v1/products', { params: { query: { q, page_size: 8 } } })),
		call(api.GET('/api/v1/services', { params: { query: { q, page_size: 6 } } }))
	]);
	return { q, results: { stores, products, services } };
};
