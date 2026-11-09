<script lang="ts">
	import { page } from '$app/state';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import CircleXIcon from '@lucide/svelte/icons/circle-x';
	import HourglassIcon from '@lucide/svelte/icons/hourglass';
	import { onMount } from 'svelte';
	import { api, call } from '#lib/api/client.js';
	import type { Order, Payment } from '#lib/api/types.js';
	import PayStores from '#lib/components/app/PayStores.svelte';
	import TestModeBadge from '#lib/components/app/TestModeBadge.svelte';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { errorMessage, fmt, m } from '#lib/i18n/state.svelte.js';
	import { needsPayment } from '#lib/payments.js';

	/**
	 * The provider redirects here with `?payment_id=…` (and an unverified `status`).
	 * The query string is never trusted: the backend syncs the payment with the
	 * provider and returns the verified state.
	 */
	const paymentId = $derived(page.url.searchParams.get('payment_id'));
	let payment = $state<Payment | null>(null);
	let order = $state<Order | null>(null);
	let error = $state<string | null>(null);
	let checking = $state(true);

	const PENDING = new Set(['CREATED', 'PENDING', 'AUTHORIZED']);
	const outcome = $derived(
		!payment
			? null
			: ['PAID', 'PARTIALLY_REFUNDED', 'REFUNDED'].includes(payment.status)
				? 'paid'
				: PENDING.has(payment.status)
					? 'pending'
					: 'failed'
	);
	const remaining = $derived(order ? order.merchant_orders.filter(needsPayment) : []);

	async function verify(id: string) {
		checking = true;
		error = null;
		try {
			let p = await call(
				api.POST('/api/v1/payments/{payment_id}/sync', { params: { path: { payment_id: id } } })
			);
			// Webhooks may lag a moment behind the redirect; re-check briefly while pending.
			for (let i = 0; i < 4 && PENDING.has(p.status); i++) {
				await new Promise((r) => setTimeout(r, 1500));
				p = await call(
					api.POST('/api/v1/payments/{payment_id}/sync', { params: { path: { payment_id: id } } })
				);
			}
			payment = p;
			order = await call(
				api.GET('/api/v1/orders/{order_id}', { params: { path: { order_id: p.order_id } } })
			);
		} catch (e) {
			error = errorMessage(e);
		} finally {
			checking = false;
		}
	}

	onMount(() => {
		if (paymentId) void verify(paymentId);
		else {
			checking = false;
			error = m().errors.notFoundBody;
		}
	});
</script>

<svelte:head><title>{m().checkout.resultTitle} · {m().brand.name}</title></svelte:head>

<div class="container-page max-w-2xl py-16">
	{#if checking}
		<Empty.Root class="py-16" role="status" aria-live="polite">
			<Empty.Header>
				<Empty.Media><Spinner class="size-8 text-primary" /></Empty.Media>
				<h1 class="type-title">{m().checkout.resultTitle}</h1>
				<Empty.Description>{m().checkout.verifying}</Empty.Description>
			</Empty.Header>
		</Empty.Root>
	{:else if error || !payment}
		<Empty.Root role="alert">
			<Empty.Header>
				<Empty.Media><CircleXIcon class="size-12 text-danger" aria-hidden="true" /></Empty.Media>
				<h1 class="font-display text-3xl">{m().checkout.resultTitle}</h1>
				<Empty.Description>{error}</Empty.Description>
			</Empty.Header>
			<Empty.Content class="flex-row justify-center">
				{#if paymentId}<Button onclick={() => verify(paymentId)}>{m().common.retry}</Button>{/if}
				<Button href="/account/orders" variant="outline">{m().nav.orders}</Button>
			</Empty.Content>
		</Empty.Root>
	{:else}
		<div class="flex flex-col gap-8" data-testid="payment-result" data-outcome={outcome}>
			<Empty.Root class="p-0" aria-live="polite">
				<Empty.Header>
					{#if outcome === 'paid'}
						<Empty.Media
							><CircleCheckIcon class="size-14 text-success" aria-hidden="true" /></Empty.Media
						>
						<h1 class="font-display text-3xl">{m().checkout.resultPaid}</h1>
						<Empty.Description>{m().checkout.resultPaidBody}</Empty.Description>
					{:else if outcome === 'pending'}
						<Empty.Media
							><HourglassIcon class="size-14 text-warning" aria-hidden="true" /></Empty.Media
						>
						<h1 class="font-display text-3xl">{m().checkout.resultPending}</h1>
						<Empty.Description>{m().checkout.resultPendingBody}</Empty.Description>
					{:else}
						<Empty.Media><CircleXIcon class="size-14 text-danger" aria-hidden="true" /></Empty.Media
						>
						<h1 class="font-display text-3xl">{m().checkout.resultFailed}</h1>
						<Empty.Description>{m().checkout.resultFailedBody}</Empty.Description>
					{/if}
				</Empty.Header>
				<Empty.Content class="flex-row justify-center text-sm text-ink-3 tabular">
					{fmt.money(payment.amount)}
					{#if payment.is_test}<TestModeBadge />{/if}
				</Empty.Content>
			</Empty.Root>

			{#if order && remaining.length}
				<section class="flex flex-col gap-3">
					<h2 class="font-medium">{m().checkout.remaining}</h2>
					<PayStores {order} />
				</section>
			{/if}

			<div class="flex flex-wrap justify-center gap-2">
				{#if outcome === 'pending'}<Button variant="outline" onclick={() => verify(payment!.id)}
						>{m().common.retry}</Button
					>{/if}
				<Button href="/account/orders/{payment.order_id}" data-testid="view-order"
					>{m().checkout.viewOrder}</Button
				>
				<Button href="/stores" variant="ghost">{m().cart.continueShopping}</Button>
			</div>
		</div>
	{/if}
</div>
