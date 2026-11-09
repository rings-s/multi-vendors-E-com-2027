import { API_URL } from '$app/env/private';
import { SIDEBAR_COOKIE_NAME } from '#lib/components/ui/sidebar/constants.js';
import type { LayoutServerLoad } from './$types';

interface Health {
	payment_provider: string;
	mock_payments: boolean;
}

// The provider never changes while the backend runs; cache it briefly per server process.
let health: { value: Health; at: number } | null = null;

async function paymentProvider(): Promise<Health> {
	if (health && Date.now() - health.at < 60_000) return health.value;
	try {
		const res = await fetch(`${API_URL}/health`);
		if (res.ok) {
			const body = (await res.json()) as Health;
			health = {
				value: { payment_provider: body.payment_provider, mock_payments: body.mock_payments },
				at: Date.now()
			};
			return health.value;
		}
	} catch {
		// Backend unavailable: pages will surface their own errors.
	}
	return { payment_provider: 'unknown', mock_payments: false };
}

export const load: LayoutServerLoad = async ({ locals, cookies }) => ({
	user: locals.user,
	locale: locals.locale,
	theme: locals.theme,
	// Dashboard sidebar expanded/collapsed, remembered so SSR renders the right width (no flash).
	sidebarOpen: cookies.get(SIDEBAR_COOKIE_NAME) !== 'false',
	payments: await paymentProvider()
});
