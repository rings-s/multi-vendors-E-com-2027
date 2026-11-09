import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

const PERIODS = [7, 30, 90, 365];

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const requested = Number(url.searchParams.get('days'));
	const days = PERIODS.includes(requested) ? requested : 30;
	return {
		earnings: await must(api.GET('/api/v1/merchant/earnings', { params: { query: { days } } })),
		days,
		periods: PERIODS
	};
};
