import { goto, invalidateAll } from '$app/navigation';
import { toast } from 'svelte-sonner';
import { api } from '#lib/api/client.js';
import { cart } from '#lib/cart.svelte.js';
import { m } from '#lib/i18n/state.svelte.js';

export async function signOut() {
	await api.POST('/api/v1/auth/logout').catch(() => {});
	cart.clear();
	toast.success(m().auth.signedOut);
	await goto('/', { invalidateAll: true });
}

/** After a successful login/registration: reload layout data, then navigate. */
export async function afterSignIn(next: string) {
	await invalidateAll();
	await goto(next, { invalidateAll: true });
}
