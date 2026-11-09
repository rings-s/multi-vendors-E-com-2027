import { call, createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:onboarding');
	const api = createApi(fetch, url.origin);
	const [onboarding, history, categories] = await Promise.all([
		must(api.GET('/api/v1/merchants/onboarding')),
		must(api.GET('/api/v1/merchants/onboarding/history')),
		call(api.GET('/api/v1/categories'))
	]);
	return { onboarding, history, categories };
};
