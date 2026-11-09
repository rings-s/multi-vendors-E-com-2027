import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:webhooks');
	const api = createApi(fetch, url.origin);
	const status = url.searchParams.get('status') ?? '';
	return {
		events: await must(
			api.GET('/api/v1/admin/webhook-events', {
				params: { query: { status: status || undefined, page: pageParam(url), page_size: 25 } }
			})
		),
		status
	};
};
