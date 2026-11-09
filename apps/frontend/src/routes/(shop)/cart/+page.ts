import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import { isCustomer } from '#lib/auth.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, parent }) => {
	const { user } = await parent();
	if (!user || !isCustomer(user)) return { quote: null };
	const api = createApi(fetch, url.origin);
	return { quote: await must(api.GET('/api/v1/cart')) };
};
