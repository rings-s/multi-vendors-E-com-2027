import { call, createApi } from '#lib/api/client.js';
import { must, pageParam } from '#lib/api/load.js';
import type { PageLoad } from './$types';

type Scope = 'GLOBAL' | 'CATEGORY' | 'MERCHANT';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:commissions');
	const api = createApi(fetch, url.origin);
	const scope = url.searchParams.get('scope') ?? '';
	const [rules, categories] = await Promise.all([
		must(
			api.GET('/api/v1/admin/commissions', {
				params: {
					query: {
						scope: (scope || undefined) as Scope | undefined,
						page: pageParam(url),
						page_size: 25
					}
				}
			})
		),
		call(api.GET('/api/v1/categories'))
	]);
	return { rules, categories, scope };
};
