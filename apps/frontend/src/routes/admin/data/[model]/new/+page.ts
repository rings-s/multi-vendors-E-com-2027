import { error } from '@sveltejs/kit';
import { createApi } from '#lib/api/client.js';
import { must } from '#lib/api/load.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, params }) => {
	const api = createApi(fetch, url.origin);
	const schema = await must(
		api.GET('/api/v1/admin/data/models/{model}', { params: { path: { model: params.model } } })
	);
	if (!schema.can_add || !schema.user_can_manage)
		error(403, 'Forbidden', { code: 'model_add_disabled' });
	// `?field=value` pre-fills the form (e.g. "add a product image" from a product).
	return { schema, initial: Object.fromEntries(url.searchParams) };
};
