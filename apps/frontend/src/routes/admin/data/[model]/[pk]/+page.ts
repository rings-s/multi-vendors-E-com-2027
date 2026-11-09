import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params, depends }) => {
	depends('app:data-record');
	const api = createApi(fetch, url.origin);
	const { model, pk } = params;
	const [schema, row, history] = await Promise.all([
		must(api.GET('/api/v1/admin/data/models/{model}', { params: { path: { model } } })),
		must(api.GET('/api/v1/admin/data/{model}/{pk}', { params: { path: { model, pk } } })),
		// The audit trail needs `admin.audit.view`; without it the history is simply hidden.
		api
			.GET('/api/v1/admin/audit-logs', {
				params: { query: { entity_type: model, entity_id: pk, page_size: 20 } }
			})
			.then((r) => r.data ?? null)
			.catch(() => null)
	]);
	return { schema, row, history };
};
