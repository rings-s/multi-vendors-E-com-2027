<script lang="ts">
	import { isolate } from '#lib/i18n/bidi.js';
	import { page } from '$app/state';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import CreditCardIcon from '@lucide/svelte/icons/credit-card';
	import RefreshCwIcon from '@lucide/svelte/icons/refresh-cw';
	import { toast } from 'svelte-sonner';
	import type { Order } from '#lib/api/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { errorMessage, fmt, m } from '#lib/i18n/state.svelte.js';
	import {
		needsPayment,
		payMerchantOrder,
		ProviderFormRequired,
		reservationExpired
	} from '#lib/payments.js';
	import StatusBadge from './StatusBadge.svelte';

	let { order }: { order: Order } = $props();
	let busy = $state<string | null>(null);
	const mock = $derived(!!page.data.payments?.mock_payments);

	async function pay(moId: string) {
		const mo = order.merchant_orders.find((x) => x.id === moId);
		if (!mo) return;
		busy = moId;
		try {
			await payMerchantOrder(mo, mock);
		} catch (e) {
			toast.error(
				e instanceof ProviderFormRequired ? m().checkout.providerFormMissing : errorMessage(e)
			);
			busy = null;
		}
	}
</script>

<Item.Group class="gap-0 overflow-hidden rounded-2xl border border-line bg-surface">
	{#each order.merchant_orders as mo, i (mo.id)}
		{@const expired = needsPayment(mo) && reservationExpired(mo)}
		{@const failed = mo.payment && ['FAILED', 'CANCELLED'].includes(mo.payment.status)}
		{#if i > 0}<Item.Separator class="my-0" />{/if}
		<Item.Root
			role="listitem"
			class="flex-col items-stretch gap-4 rounded-none p-5 sm:flex-row sm:items-center sm:justify-between"
			data-testid="pay-row"
		>
			<Item.Content>
				<Item.Title><bdi>{mo.store_name}</bdi></Item.Title>
				<Item.Description class="tabular">
					{m().orders.storeOrder({ number: isolate(mo.number) })} · {fmt.money(mo.total)}
				</Item.Description>
				{#if failed && mo.payment?.failure_reason}<p class="text-sm text-destructive">
						{m().checkout.failed}
					</p>{/if}
				{#if needsPayment(mo) && mo.reservation_expires_at && !expired}
					<p class="text-xs text-ink-3">
						{m().checkout.reservedUntil({ time: fmt.datetime(mo.reservation_expires_at) })}
					</p>
				{/if}
			</Item.Content>
			<Item.Actions class="gap-3">
				{#if !needsPayment(mo)}
					<StatusBadge status={mo.status} />
					{#if mo.payment?.status === 'PAID'}<CircleCheckIcon
							class="size-5 text-success"
							aria-label={m().checkout.paid}
						/>{/if}
				{:else if expired}
					<p class="max-w-56 text-sm text-ink-3">{m().checkout.expired}</p>
				{:else}
					<Button onclick={() => pay(mo.id)} disabled={busy !== null} data-testid="pay-store">
						{#if busy === mo.id}
							<Spinner data-icon="inline-start" />{m().checkout.paying}
						{:else if failed}
							<RefreshCwIcon data-icon="inline-start" />{m().checkout.retryPayment}
						{:else}
							<CreditCardIcon data-icon="inline-start" />{m().checkout.payStore({
								store: isolate(mo.store_name)
							})}
						{/if}
					</Button>
				{/if}
			</Item.Actions>
		</Item.Root>
	{/each}
</Item.Group>
