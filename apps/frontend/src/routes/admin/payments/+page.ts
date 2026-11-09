import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PaymentStatus } from '#lib/api/types.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const sp = url.searchParams;
	const filters = {
		reference: sp.get('reference') ?? '',
		status: sp.get('status') ?? '',
		merchant_id: sp.get('merchant_id') ?? '',
		is_test: sp.get('is_test') ?? ''
	};
	const payments = await must(
		api.GET('/api/v1/admin/payments', {
			params: {
				query: {
					reference: filters.reference || undefined,
					status: (filters.status || undefined) as PaymentStatus | undefined,
					merchant_id: filters.merchant_id || undefined,
					is_test: filters.is_test ? filters.is_test === 'true' : undefined,
					page: pageParam(url),
					page_size: 25
				}
			}
		})
	);
	return { payments, filters };
};
