import { createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

const STATUSES = [
	'PENDING',
	'CONFIRMED',
	'PREPARING',
	'READY_FOR_PICKUP',
	'OUT_FOR_DELIVERY',
	'DELIVERED',
	'FAILED',
	'CANCELLED'
] as const;
type Status = (typeof STATUSES)[number];

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const statusParam = url.searchParams.get('status') ?? '';
	const status = (STATUSES as readonly string[]).includes(statusParam)
		? (statusParam as Status)
		: undefined;
	const methodParam = url.searchParams.get('method');
	const method = methodParam === 'DELIVERY' || methodParam === 'PICKUP' ? methodParam : undefined;
	const active = url.searchParams.get('active') !== 'false';
	const deliveries = await must(
		api.GET('/api/v1/merchant/deliveries', {
			params: { query: { status, method, active, page: pageParam(url), page_size: 20 } }
		})
	);
	return {
		deliveries,
		statuses: STATUSES,
		filters: { status: status ?? '', method: method ?? '', active }
	};
};
