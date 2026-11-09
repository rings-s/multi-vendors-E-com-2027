import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const sp = url.searchParams;
	const filters = {
		number: sp.get('number') ?? '',
		status: sp.get('status') ?? '',
		merchant_id: sp.get('merchant_id') ?? '',
		date_from: sp.get('date_from') ?? '',
		date_to: sp.get('date_to') ?? '',
		cancellation_requested: sp.get('cancellation_requested') ?? ''
	};
	const orders = await must(
		api.GET('/api/v1/admin/orders', {
			params: {
				query: {
					number: filters.number || undefined,
					status: filters.status || undefined,
					merchant_id: filters.merchant_id || undefined,
					date_from: filters.date_from || undefined,
					date_to: filters.date_to || undefined,
					cancellation_requested: filters.cancellation_requested
						? filters.cancellation_requested === 'true'
						: undefined,
					page: pageParam(url),
					page_size: 25
				}
			}
		})
	);
	return { orders, filters };
};
