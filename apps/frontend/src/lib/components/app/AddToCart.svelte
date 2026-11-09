<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import ShoppingBagIcon from '@lucide/svelte/icons/shopping-bag';
	import { toast } from 'svelte-sonner';
	import { isCustomer } from '#lib/auth.js';
	import { cart } from '#lib/cart.svelte.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { errorMessage, m } from '#lib/i18n/state.svelte.js';

	interface Props {
		item: {
			product_id?: string;
			variant_id?: string | null;
			service_id?: string;
			quantity?: number;
		};
		disabled?: boolean;
		label?: string;
	}

	let { item, disabled = false, label }: Props = $props();
	let pending = $state(false);
	const user = $derived(page.data.user);

	async function add() {
		if (!user) {
			await goto(`/sign-in?next=${encodeURIComponent(page.url.pathname + page.url.search)}`);
			return;
		}
		if (!isCustomer(user)) {
			toast.error(m().catalog.customerOnly);
			return;
		}
		pending = true;
		try {
			await cart.add(item);
			toast.success(m().catalog.added, {
				action: { label: m().nav.cart, onClick: () => goto('/cart') }
			});
		} catch (e) {
			toast.error(errorMessage(e));
		} finally {
			pending = false;
		}
	}
</script>

<div class="flex flex-col gap-2">
	<Button
		size="lg"
		class="h-12 w-full text-base"
		onclick={add}
		disabled={disabled || pending}
		data-testid="add-to-cart"
	>
		{#if pending}<Spinner data-icon="inline-start" />{m().catalog.adding}{:else}<ShoppingBagIcon
				data-icon="inline-start"
			/>{label ?? m().catalog.addToCart}{/if}
	</Button>
	{#if !user}
		<p class="text-center text-xs text-ink-3">{m().catalog.signInToBuy}</p>
	{:else if !isCustomer(user)}
		<p class="text-center text-xs text-ink-3">{m().catalog.customerOnly}</p>
	{/if}
</div>
