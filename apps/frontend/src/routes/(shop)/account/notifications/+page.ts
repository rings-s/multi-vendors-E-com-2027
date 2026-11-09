import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:notifications');
	const api = createApi(fetch, url.origin);
	const unreadOnly = url.searchParams.get('unread') === '1';
	const page = await must(
		api.GET('/api/v1/notifications', {
			params: { query: { unread_only: unreadOnly, page: pageParam(url), page_size: 20 } }
		})
	);
	return { notifications: page, unreadOnly };
};
