import { call, createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

const TABS = ['products', 'services', 'reviews', 'about'] as const;
export type StoreTab = (typeof TABS)[number];

export const load: PageLoad = async ({ fetch, url, params }) => {
	const api = createApi(fetch, url.origin);
	const tabParam = url.searchParams.get('tab') ?? 'products';
	const tab: StoreTab = (TABS as readonly string[]).includes(tabParam)
		? (tabParam as StoreTab)
		: 'products';
	const page = pageParam(url);
	const slug = params.slug;
	const sortParam = url.searchParams.get('sort');
	const sort = ['newest', 'price_asc', 'price_desc', 'popular'].includes(sortParam ?? '')
		? sortParam!
		: 'newest';

	const store = await must(api.GET('/api/v1/stores/{slug}', { params: { path: { slug } } }));
	const q = { page: tab === 'products' ? page : 1, page_size: 12, sort: sort as 'newest' };
	const [products, services, categories, locations, delivery] = await Promise.all([
		call(api.GET('/api/v1/stores/{slug}/products', { params: { path: { slug }, query: q } })),
		call(
			api.GET('/api/v1/stores/{slug}/services', {
				params: { path: { slug }, query: { ...q, page: tab === 'services' ? page : 1 } }
			})
		),
		call(api.GET('/api/v1/categories')),
		// Pickup points are supplementary: never fail the storefront over them.
		call(api.GET('/api/v1/stores/{slug}/locations', { params: { path: { slug } } })).catch(
			() => []
		),
		call(api.GET('/api/v1/stores/{slug}/delivery', { params: { path: { slug } } })).catch(
			() => null
		)
	]);
	// Reviews are secondary: stream them so the storefront renders immediately.
	const reviews = call(
		api.GET('/api/v1/stores/{slug}/reviews', {
			params: { path: { slug }, query: { page: tab === 'reviews' ? page : 1, page_size: 10 } }
		})
	);
	return { store, products, services, reviews, categories, locations, delivery, tab, sort };
};
