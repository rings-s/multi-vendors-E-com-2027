import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

type TicketStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:admin-tickets');
	const api = createApi(fetch, url.origin);
	const status = url.searchParams.get('status') ?? '';
	return {
		tickets: await must(
			api.GET('/api/v1/admin/support-tickets', {
				params: {
					query: {
						status: (status || undefined) as TicketStatus | undefined,
						page: pageParam(url),
						page_size: 20
					}
				}
			})
		),
		status
	};
};
