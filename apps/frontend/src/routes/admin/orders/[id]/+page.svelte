<script lang="ts">
	import { isolate } from '#lib/i18n/bidi.js';
	import { invalidate } from '$app/navigation';
	import { api, call } from '#lib/api/client.js';
	import DeliveryCard from '#lib/components/app/DeliveryCard.svelte';
	import OrderItemsTable from '#lib/components/app/OrderItemsTable.svelte';
	import OrderSummary from '#lib/components/app/OrderSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { prompt } from '#lib/confirm.svelte.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const order = $derived(data.detail.order);
	const t = $derived(m().admin);
	let busy = $state(false);

	async function decide(moId: string, approve: boolean) {
		const note = await prompt({
			title: approve ? m().merchant.approveCancellation : m().merchant.declineCancellation,
			label: m().common.note,
			optional: true,
			destructive: approve
		});
		if (note == null) return;
		busy = true;
		await action(
			() =>
				call(
					api.POST('/api/v1/admin/merchant-orders/{mo_id}/cancellation-decision', {
						params: { path: { mo_id: moId } },
						body: { approve, note: note || null }
					})
				),
			m().merchant.fulfillmentUpdated
		);
		busy = false;
		await invalidate('app:admin-order');
	}
	const historyFor = (moId: string) =>
		data.detail.history.filter((h) => h.merchant_order_id === moId);
</script>

<svelte:head
	><title>{m().orders.detailTitle({ number: isolate(order.number) })} · {t.title}</title
	></svelte:head
>

<div class="flex flex-col gap-8">
	<PageHeader title={m().orders.detailTitle({ number: isolate(order.number) })}>
		{#snippet meta()}<div class="flex items-center gap-3 text-sm text-ink-3">
				<StatusBadge status={order.status} />{fmt.datetime(order.created_at)} · {order.contact_name} ·
				<span dir="ltr">{order.contact_email}</span>
			</div>{/snippet}
	</PageHeader>

	<div class="grid gap-8 lg:grid-cols-[1fr_18rem]">
		<div class="flex flex-col gap-6">
			{#each order.merchant_orders as mo (mo.id)}
				<Card.Root class="gap-0">
					<Card.Header class="border-b">
						<Card.Title><bdi>{mo.store_name}</bdi></Card.Title>
						<Card.Description class="text-xs" dir="ltr">{mo.number}</Card.Description>
						<Card.Action class="flex items-center gap-2">
							<StatusBadge status={mo.status} />{#if mo.payment}<StatusBadge
									status={mo.payment.status}
								/>{/if}
						</Card.Action>
					</Card.Header>
					{#if mo.cancellation_status === 'REQUESTED'}
						<Alert.Root
							variant="warning"
							role="status"
							class="rounded-none border-x-0 border-t-0 px-5 py-3"
						>
							<Alert.Description>{m().merchant.cancellationRequest}</Alert.Description>
							<Alert.Action class="flex gap-2">
								<Button
									size="sm"
									variant="destructive"
									disabled={busy}
									onclick={() => decide(mo.id, true)}>{m().merchant.approveCancellation}</Button
								>
								<Button
									size="sm"
									variant="outline"
									disabled={busy}
									onclick={() => decide(mo.id, false)}>{m().merchant.declineCancellation}</Button
								>
							</Alert.Action>
						</Alert.Root>
					{/if}
					<OrderItemsTable items={mo.items} />
					<Separator />
					<Card.Content class="grid gap-6 pt-(--card-spacing) md:grid-cols-2">
						<ol class="flex flex-col gap-2 border-s border-line ps-4 text-sm">
							{#each historyFor(mo.id) as h, i (i)}<li>
									<span class="font-medium">{statusLabel(h.to_status)}</span>
									<span class="text-ink-3">· {fmt.datetime(h.created_at)}</span>{#if h.note}<p
											class="text-ink-2"
										>
											<bdi>{h.note}</bdi>
										</p>{/if}
								</li>{/each}
						</ol>
						<OrderSummary
							subtotal={mo.items_subtotal}
							discount={mo.discount_total}
							delivery={mo.delivery_fee}
							deliveryMethod={mo.delivery_method}
							vat={mo.vat_total}
							total={mo.total}
							vatRate={mo.vat_rate}
						/>
					</Card.Content>
				</Card.Root>
				{#if mo.delivery}<DeliveryCard delivery={mo.delivery} showTerms />{/if}
			{/each}
			<section class="flex flex-col gap-3">
				<h2 class="type-title">{t.payments}</h2>
				<Item.Group class="gap-0 overflow-hidden rounded-2xl border border-line bg-surface">
					{#each data.detail.payments as p, i (p.id)}
						{#if i > 0}<Item.Separator class="my-0" />{/if}
						<Item.Root role="listitem" class="rounded-none p-4">
							{#snippet child({ props })}
								<a href="/admin/payments/{p.id}" {...props}>
									<Item.Content>
										<Item.Title class="tabular" dir="ltr"
											>{p.provider_payment_id ?? p.id.slice(0, 8)}</Item.Title
										>
										<Item.Description>{fmt.datetime(p.created_at)}</Item.Description>
									</Item.Content>
									<Item.Actions class="gap-3">
										<span class="tabular">{fmt.money(p.amount)}</span>
										<StatusBadge status={p.status} />
									</Item.Actions>
								</a>
							{/snippet}
						</Item.Root>
					{:else}
						<Item.Root role="listitem" class="p-4">
							<Item.Description>—</Item.Description>
						</Item.Root>
					{/each}
				</Item.Group>
			</section>
		</div>
		<aside class="h-fit">
			<Card.Root class="h-full">
				<Card.Content>
					<OrderSummary
						subtotal={order.items_subtotal}
						discount={order.discount_total}
						delivery={order.delivery_total}
						deliveryMethod={order.merchant_orders.some((x) => x.delivery_method !== 'NONE')
							? 'DELIVERY'
							: 'NONE'}
						vat={order.vat_total}
						total={order.total}
					/>
				</Card.Content>
			</Card.Root>
		</aside>
	</div>
</div>
