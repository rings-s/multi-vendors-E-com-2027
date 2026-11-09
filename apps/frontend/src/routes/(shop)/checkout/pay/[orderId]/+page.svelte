<script lang="ts">
	import { page } from '$app/state';
	import OrderSummary from '#lib/components/app/OrderSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import PayStores from '#lib/components/app/PayStores.svelte';
	import TestModeBadge from '#lib/components/app/TestModeBadge.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { needsPayment } from '#lib/payments.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const order = $derived(data.order);
	const outstanding = $derived(order.merchant_orders.filter(needsPayment).length);
	const mock = $derived(!!page.data.payments?.mock_payments);
</script>

<svelte:head><title>{m().checkout.payTitle} · {m().brand.name}</title></svelte:head>

<div class="container-page max-w-4xl py-12">
	<PageHeader
		title={m().checkout.payTitle}
		description={outstanding ? m().checkout.payIntro : m().checkout.allPaid}
	>
		{#snippet meta()}
			<p class="text-sm text-ink-3 tabular">
				{m().orders.number}: <span dir="ltr">{order.number}</span>
			</p>
		{/snippet}
		{#snippet actions()}{#if mock}<TestModeBadge />{/if}{/snippet}
	</PageHeader>
	<div class="mt-8 grid gap-8 md:grid-cols-[1fr_18rem]">
		<PayStores {order} />
		<aside class="h-fit">
			<Card.Root class="h-full">
				<Card.Content class="flex flex-col gap-4">
					<OrderSummary
						subtotal={order.items_subtotal}
						discount={order.discount_total}
						delivery={order.delivery_total}
						deliveryMethod={order.merchant_orders.some((mo) => mo.delivery_method === 'DELIVERY')
							? 'DELIVERY'
							: order.merchant_orders.some((mo) => mo.delivery_method === 'PICKUP')
								? 'PICKUP'
								: 'NONE'}
						vat={order.vat_total}
						total={order.total}
					/>
					<Button href="/account/orders/{order.id}" variant="outline" class="w-full"
						>{m().checkout.viewOrder}</Button
					>
				</Card.Content>
			</Card.Root>
		</aside>
	</div>
</div>
