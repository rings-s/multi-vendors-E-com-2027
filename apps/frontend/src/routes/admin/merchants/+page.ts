import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { MerchantStatus } from '#lib/api/types.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const status = url.searchParams.get('status') ?? '';
	const q = url.searchParams.get('q') ?? '';
	const merchants = await must(
		api.GET('/api/v1/admin/merchants', {
			params: {
				query: {
					status: (status || undefined) as MerchantStatus | undefined,
					q: q || undefined,
					page: pageParam(url),
					page_size: 25
				}
			}
		})
	);
	return { merchants, filters: { status, q } };
};
