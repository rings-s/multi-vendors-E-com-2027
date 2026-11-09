import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { MerchantOrderStatus } from '#lib/api/types.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const status = url.searchParams.get('status') ?? '';
	const includeUnpaid = url.searchParams.get('include_unpaid') === 'true';
	const orders = await must(
		api.GET('/api/v1/merchant/orders', {
			params: {
				query: {
					status: (status || undefined) as MerchantOrderStatus | undefined,
					include_unpaid: includeUnpaid,
					page: pageParam(url),
					page_size: 20
				}
			}
		})
	);
	return { orders, filters: { status, includeUnpaid } };
};
