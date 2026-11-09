import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { RefundStatus } from '#lib/api/types.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:admin-refunds');
	const api = createApi(fetch, url.origin);
	const status = url.searchParams.get('status') ?? '';
	return {
		refunds: await must(
			api.GET('/api/v1/admin/refunds', {
				params: {
					query: {
						status: (status || undefined) as RefundStatus | undefined,
						page: pageParam(url),
						page_size: 25
					}
				}
			})
		),
		status
	};
};
