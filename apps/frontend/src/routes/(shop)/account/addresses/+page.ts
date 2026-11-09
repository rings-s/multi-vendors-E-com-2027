import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:addresses');
	const api = createApi(fetch, url.origin);
	return { addresses: await must(api.GET('/api/v1/customers/addresses')) };
};
