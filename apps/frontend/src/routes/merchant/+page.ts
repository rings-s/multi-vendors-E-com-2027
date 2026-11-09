import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import { ANALYTICS_PERIODS, periodParam } from '#lib/charts/periods.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const api = createApi(fetch, url.origin);
	const days = periodParam(url);
	const [dashboard, analytics] = await Promise.all([
		must(api.GET('/api/v1/merchant/dashboard')),
		must(api.GET('/api/v1/merchant/analytics', { params: { query: { days } } }))
	]);
	return { dashboard, analytics, periods: ANALYTICS_PERIODS };
};
