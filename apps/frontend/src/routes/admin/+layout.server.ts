import { requireUser } from '#lib/auth.js';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = ({ locals, url }) => {
	requireUser(locals, url, 'ADMIN', 'SUPER_ADMIN');
	return {};
};
