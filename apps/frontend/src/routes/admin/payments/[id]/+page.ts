import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params, depends }) => {
	depends('app:admin-payment');
	const api = createApi(fetch, url.origin);
	return {
		payment: await must(
			api.GET('/api/v1/admin/payments/{payment_id}', {
				params: { path: { payment_id: params.id } }
			})
		)
	};
};
