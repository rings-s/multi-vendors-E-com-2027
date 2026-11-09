import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:payment-account');
	const api = createApi(fetch, url.origin);
	return { account: await must(api.GET('/api/v1/merchants/payment-account')) };
};
