import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { SettlementStatus } from '#lib/api/types.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:admin-settlements');
	const api = createApi(fetch, url.origin);
	const status = url.searchParams.get('status') ?? '';
	const merchant_id = url.searchParams.get('merchant_id') ?? '';
	const settlements = await must(
		api.GET('/api/v1/admin/settlements', {
			params: {
				query: {
					status: (status || undefined) as SettlementStatus | undefined,
					merchant_id: merchant_id || undefined,
					page: pageParam(url),
					page_size: 25
				}
			}
		})
	);
	return { settlements, filters: { status, merchant_id } };
};
