import { call, createApi } from '#lib/api/client.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	return { home: await call(api.GET('/api/v1/homepage')) };
};
