import { redirect } from '@sveltejs/kit';
import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const [quote, addresses, me] = await Promise.all([
		must(api.GET('/api/v1/cart')),
		must(api.GET('/api/v1/customers/addresses')),
		must(api.GET('/api/v1/customers/me'))
	]);
	if (!quote.groups.length) redirect(303, '/cart');
	return { quote, addresses, me };
};
