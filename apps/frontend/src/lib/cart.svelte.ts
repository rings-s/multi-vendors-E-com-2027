/**
 * Client-side cart badge state. The cart itself lives on the server (`/cart`); every
 * mutation returns the recalculated quote, which is the only source of totals.
 */
import { api, call } from '#lib/api/client.js';
import type { Quote } from '#lib/api/types.js';

class CartState {
	count = $state(0);
	loaded = $state(false);

	set(quote: Quote | null | undefined) {
		this.count = quote?.item_count ?? 0;
		this.loaded = true;
	}

	async refresh() {
		try {
			this.set(await call(api.GET('/api/v1/cart')));
		} catch {
			this.set(null);
		}
	}

	async add(item: {
		product_id?: string;
		variant_id?: string | null;
		service_id?: string;
		quantity?: number;
	}) {
		const quote = await call(api.POST('/api/v1/cart/items', { body: { quantity: 1, ...item } }));
		this.set(quote);
		return quote;
	}

	clear() {
		this.count = 0;
	}
}

export const cart = new CartState();
