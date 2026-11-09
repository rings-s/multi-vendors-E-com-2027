import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const sp = url.searchParams;
	const filters = {
		action: sp.get('action') ?? '',
		entity_type: sp.get('entity_type') ?? '',
		entity_id: sp.get('entity_id') ?? ''
	};
	const logs = await must(
		api.GET('/api/v1/admin/audit-logs', {
			params: {
				query: {
					action: filters.action || undefined,
					entity_type: filters.entity_type || undefined,
					entity_id: filters.entity_id || undefined,
					page: pageParam(url),
					page_size: 30
				}
			}
		})
	);
	return { logs, filters };
};
