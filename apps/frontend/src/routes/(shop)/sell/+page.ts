import { redirect } from '@sveltejs/kit';
import { call, createApi } from '#lib/api/client.js';
import { isMerchant } from '#lib/auth.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, parent }) => {
	const { user } = await parent();
	if (isMerchant(user)) redirect(303, '/merchant');
	const api = createApi(fetch, url.origin);
	return { categories: await call(api.GET('/api/v1/categories')) };
};
