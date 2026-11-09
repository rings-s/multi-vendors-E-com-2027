import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params, depends }) => {
	depends('app:admin-merchant');
	const api = createApi(fetch, url.origin);
	return {
		detail: await must(
			api.GET('/api/v1/admin/merchants/{merchant_id}', {
				params: { path: { merchant_id: params.id } }
			})
		)
	};
};
