import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params }) => {
	const api = createApi(fetch, url.origin);
	const service = await must(
		api.GET('/api/v1/services/{service_id}', { params: { path: { service_id: params.id } } })
	);
	return { service };
};
