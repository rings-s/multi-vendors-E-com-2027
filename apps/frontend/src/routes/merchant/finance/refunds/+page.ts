import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { RefundStatus } from '#lib/api/types.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:refunds');
	const api = createApi(fetch, url.origin);
	const status = url.searchParams.get('status') ?? '';
	const refunds = await must(
		api.GET('/api/v1/merchant/refunds', {
			params: {
				query: {
					status: (status || undefined) as RefundStatus | undefined,
					page: pageParam(url),
					page_size: 25
				}
			}
		})
	);
	return { refunds, status };
};
