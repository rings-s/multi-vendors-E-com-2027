import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:settings');
	const api = createApi(fetch, url.origin);
	return {
		settings: (await must(api.GET('/api/v1/admin/settings'))) as Record<
			string,
			Record<string, unknown>
		>
	};
};
