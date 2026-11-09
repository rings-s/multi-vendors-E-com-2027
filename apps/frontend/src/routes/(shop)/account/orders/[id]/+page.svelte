<script lang="ts">
	import { isolate } from '#lib/i18n/bidi.js';
	import { invalidate } from '$app/navigation';
	import BanIcon from '@lucide/svelte/icons/ban';
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import ReceiptIcon from '@lucide/svelte/icons/receipt';
	import StarIcon from '@lucide/svelte/icons/star';
	import Undo2Icon from '@lucide/svelte/icons/undo-2';
	import { api, call } from '#lib/api/client.js';
	import type { MerchantOrderCustomerView } from '#lib/api/types.js';
	import DeliveryCard from '#lib/components/app/DeliveryCard.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import OrderSummary from '#lib/components/app/OrderSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import PayStores from '#lib/components/app/PayStores.svelte';
	import StarInput from '#lib/components/app/StarInput.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import TestModeBadge from '#lib/components/app/TestModeBadge.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Collapsible from '#lib/components/ui/collapsible/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { prompt } from '#lib/confirm.svelte.js';
	import { sarToHalalas } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import { needsPayment } from '#lib/payments.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const order = $derived(data.order);
	const outstanding = $derived(order.merchant_orders.some(needsPayment));
	const address = $derived(order.delivery_address as Record<string, string> | null);
	const isTest = $derived(order.merchant_orders.some((mo) => mo.payment?.is_test));

	const CANCELLABLE = new Set(['PAID', 'ACCEPTED', 'PROCESSING']);
	const REVIEWABLE = new Set(['DELIVERED', 'COMPLETED']);
	const canCancel = (mo: MerchantOrderCustomerView) =>
		CANCELLABLE.has(mo.status) && mo.cancellation_status === 'NONE';
	const canRefund = (mo: MerchantOrderCustomerView) =>
		!!mo.payment &&
		['PAID', 'PARTIALLY_REFUNDED'].includes(mo.payment.status) &&
		mo.status !== 'PENDING_PAYMENT';
	const refresh = () => invalidate('app:order');

	async function cancel(mo: MerchantOrderCustomerView) {
		const reason = await prompt({
			title: m().orders.requestCancellation,
			label: m().orders.cancellationReason,
			minLength: 3,
			destructive: true
		});
		if (reason == null) return;
		const ok = await action(
			() =>
				call(
					api.POST('/api/v1/orders/{order_id}/merchant-orders/{mo_id}/cancel', {
						params: { path: { order_id: order.id, mo_id: mo.id } },
						body: { reason }
					})
				),
			m().orders.cancellationRequested
		);
		if (ok) await refresh();
	}

	// Refund request dialog
	let refundFor = $state<MerchantOrderCustomerView | null>(null);
	let refundAmount = $state('');
	let refundReason = $state('');
	const refundForm = new FormState();
	async function submitRefund(e: SubmitEvent) {
		e.preventDefault();
		if (!refundFor) return;
		refundForm.reset();
		const amount = refundAmount.trim() ? sarToHalalas(refundAmount) : null;
		if (refundAmount.trim() && !amount) return refundForm.fail('amount', m().errors.invalidAmount);
		if (refundReason.trim().length < 3)
			return refundForm.fail('reason', m().errors.codes.reason_required);
		const mo = refundFor;
		const res = await refundForm.submit(
			() =>
				call(
					api.POST('/api/v1/orders/{order_id}/merchant-orders/{mo_id}/refund-requests', {
						params: { path: { order_id: order.id, mo_id: mo.id } },
						body: { amount, scope: 'AUTO', reason: refundReason.trim() }
					})
				),
			{ success: m().orders.refundRequested }
		);
		if (res.ok) {
			refundFor = null;
			await refresh();
		}
	}

	// Review dialog
	let reviewFor = $state<MerchantOrderCustomerView | null>(null);
	let rating = $state(5);
	let comment = $state('');
	const reviewForm = new FormState();
	async function submitReview(e: SubmitEvent) {
		e.preventDefault();
		if (!reviewFor) return;
		const mo = reviewFor;
		const res = await reviewForm.submit(
			() =>
				call(
					api.POST('/api/v1/orders/{order_id}/merchant-orders/{mo_id}/review', {
						params: { path: { order_id: order.id, mo_id: mo.id } },
						body: { rating, comment }
					})
				),
			{ success: m().orders.reviewSent }
		);
		if (res.ok) reviewFor = null;
	}

	const storeHistory = (moId: string) => data.history.filter((h) => h.merchant_order_id === moId);
</script>

<svelte:head
	><title>{m().orders.detailTitle({ number: isolate(order.number) })} · {m().brand.name}</title
	></svelte:head
>

<div class="flex flex-col gap-8">
	<PageHeader title={m().orders.detailTitle({ number: isolate(order.number) })}>
		{#snippet meta()}
			<div class="flex flex-wrap items-center gap-3 text-sm text-ink-3">
				<StatusBadge status={order.status} />
				<span>{m().orders.placed}: {fmt.datetime(order.created_at)}</span>
				{#if isTest}<TestModeBadge />{/if}
			</div>
		{/snippet}
	</PageHeader>

	{#if outstanding}
		<section class="flex flex-col gap-3" aria-labelledby="pay-h">
			<h2 id="pay-h" class="font-medium">{m().checkout.payTitle}</h2>
			<PayStores {order} />
		</section>
	{/if}

	<div class="grid gap-8 lg:grid-cols-[1fr_18rem]">
		<div class="flex flex-col gap-6">
			{#each order.merchant_orders as mo (mo.id)}
				<Card.Root
					role="region"
					aria-labelledby="mo-{mo.id}"
					data-testid="merchant-order"
					class="gap-0"
				>
					<Card.Header class="border-b">
						<Card.Title role="heading" aria-level={2} id="mo-{mo.id}">
							<a href="/stores/{mo.store_slug}" class="hover:underline"
								><bdi>{mo.store_name}</bdi></a
							>
						</Card.Title>
						<Card.Description class="text-xs tabular" dir="ltr">{mo.number}</Card.Description>
						<Card.Action class="flex flex-wrap items-center gap-2">
							<StatusBadge status={mo.status} />
							{#if mo.cancellation_status !== 'NONE'}
								<StatusBadge
									status={mo.cancellation_status}
									label="{m().orders.cancellationStatus}: {statusLabel(mo.cancellation_status)}"
								/>
							{/if}
						</Card.Action>
					</Card.Header>

					<Table.Root>
						<Table.Header>
							<Table.Row>
								<Table.Head>{m().orders.items}</Table.Head>
								<Table.Head class="text-end">{m().orders.qty}</Table.Head>
								<Table.Head class="text-end">{m().orders.unitPrice}</Table.Head>
								<Table.Head class="text-end">{m().orders.lineTotal}</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each mo.items as item (item.id)}
								<Table.Row>
									<Table.Cell class="max-w-64 whitespace-normal">
										<p class="font-medium"><bdi>{item.title}</bdi></p>
										{#if item.sku}<p class="text-xs text-ink-3" dir="ltr">{item.sku}</p>{/if}
									</Table.Cell>
									<Table.Cell class="text-end tabular">{fmt.number(item.quantity)}</Table.Cell>
									<Table.Cell class="text-end tabular"
										>{fmt.money(item.unit_price - item.unit_discount)}</Table.Cell
									>
									<Table.Cell class="text-end tabular">{fmt.money(item.line_total)}</Table.Cell>
								</Table.Row>
							{/each}
						</Table.Body>
					</Table.Root>

					<Separator />
					<Card.Content class="grid gap-6 pt-(--card-spacing) md:grid-cols-2">
						<div class="flex flex-col gap-4 text-sm">
							{#if mo.payment}
								<div class="flex flex-col gap-1">
									<p class="text-ink-3">{m().orders.payment}</p>
									<div class="flex items-center gap-2">
										<StatusBadge status={mo.payment.status} />{#if mo.refunded_amount}<span
												class="text-ink-2 tabular"
												>{m().orders.refunded}: {fmt.money(mo.refunded_amount)}</span
											>{/if}
									</div>
								</div>
							{/if}
							{#each mo.shipments as s (s.id)}
								<div class="flex flex-col gap-1">
									<p class="text-ink-3">{m().orders.shipment}</p>
									<p>
										{s.carrier}
										{#if s.tracking_number}· <span dir="ltr" class="tabular"
												>{s.tracking_number}</span
											>{/if}
									</p>
									{#if s.tracking_url}<a
											href={s.tracking_url}
											target="_blank"
											rel="noopener noreferrer"
											class="inline-flex items-center gap-1 text-primary hover:underline"
											>{m().orders.tracking}<ExternalLinkIcon
												class="size-3.5"
												aria-hidden="true"
											/></a
										>{/if}
								</div>
							{/each}
							{#if storeHistory(mo.id).length}
								<Collapsible.Root>
									<Collapsible.Trigger>
										{#snippet child({ props })}
											<Button {...props} variant="link" size="sm" class="group px-0"
												>{m().orders.history}<ChevronDownIcon
													data-icon="inline-end"
													class="transition-transform group-data-[state=open]:rotate-180"
												/></Button
											>
										{/snippet}
									</Collapsible.Trigger>
									<Collapsible.Content>
										<ol class="mt-3 flex flex-col gap-2 border-s border-line ps-4">
											{#each storeHistory(mo.id) as h, i (i)}
												<li class="flex flex-col gap-0.5">
													<p class="font-medium">{statusLabel(h.to_status)}</p>
													<p class="text-xs text-ink-3">
														{fmt.datetime(h.created_at)}{#if h.note}
															· <bdi>{h.note}</bdi>{/if}
													</p>
												</li>
											{/each}
										</ol>
									</Collapsible.Content>
								</Collapsible.Root>
							{/if}
						</div>
						<div class="flex flex-col gap-4">
							<OrderSummary
								subtotal={mo.items_subtotal}
								discount={mo.discount_total}
								delivery={mo.delivery_fee}
								deliveryMethod={mo.delivery_method}
								vat={mo.vat_total}
								total={mo.total}
								vatRate={mo.vat_rate}
							/>
							<div class="flex flex-wrap gap-2">
								{#if mo.payment?.status === 'PAID' || mo.payment?.status === 'PARTIALLY_REFUNDED' || mo.payment?.status === 'REFUNDED'}
									<Button
										href="/api/v1/orders/{order.id}/merchant-orders/{mo.id}/receipt"
										variant="outline"
										size="sm"
										download
										data-sveltekit-reload
									>
										<ReceiptIcon data-icon="inline-start" />{m().orders.receipt}
									</Button>
								{/if}
								{#if canCancel(mo)}
									<Button variant="outline" size="sm" onclick={() => cancel(mo)}
										><BanIcon data-icon="inline-start" />{m().orders.requestCancellation}</Button
									>
								{/if}
								{#if canRefund(mo)}
									<Button
										variant="outline"
										size="sm"
										onclick={() => {
											refundFor = mo;
											refundAmount = '';
											refundReason = '';
											refundForm.reset();
										}}><Undo2Icon data-icon="inline-start" />{m().orders.requestRefund}</Button
									>
								{/if}
								{#if REVIEWABLE.has(mo.status)}
									<Button
										variant="outline"
										size="sm"
										onclick={() => {
											reviewFor = mo;
											rating = 5;
											comment = '';
										}}><StarIcon data-icon="inline-start" />{m().orders.review}</Button
									>
								{/if}
							</div>
						</div>
					</Card.Content>
				</Card.Root>
				{#if mo.delivery}
					<DeliveryCard delivery={mo.delivery} />
				{/if}
			{/each}
		</div>

		<aside class="h-fit">
			<Card.Root class="h-full">
				<Card.Content class="flex flex-col gap-6 text-sm">
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
					<div class="flex flex-col gap-1">
						<p class="text-ink-3">{m().orders.contact}</p>
						<p>{order.contact_name}</p>
						<p dir="ltr" class="text-start tabular">{fmt.phone(order.contact_phone)}</p>
						<p dir="ltr" class="text-start">{order.contact_email}</p>
					</div>
					{#if address}
						<div class="flex flex-col gap-1">
							<p class="text-ink-3">{m().orders.deliveryTo}</p>
							<p><bdi>{address.recipient_name}</bdi></p>
							<p class="text-ink-2">
								{fmt.list([
									address.street,
									address.building_number,
									address.district,
									address.city,
									fmt.region(address.region),
									address.postal_code
								])}
							</p>
						</div>
					{/if}
				</Card.Content>
			</Card.Root>
		</aside>
	</div>
</div>

<Dialog.Root open={!!refundFor} onOpenChange={(o) => !o && (refundFor = null)}>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={submitRefund} novalidate>
			<Dialog.Header>
				<Dialog.Title>{m().orders.requestRefund}</Dialog.Title>
				<Dialog.Description
					><bdi>{refundFor?.store_name}</bdi> · {fmt.money(refundFor?.total)}</Dialog.Description
				>
			</Dialog.Header>
			<Field.Group>
				<FormField
					label={m().orders.refundAmount}
					id="refund-amount"
					error={refundForm.errors.amount}
					hint={m().orders.refundAmountHint}
					optional
				>
					{#snippet children({ id, invalid, describedBy })}
						<Input
							{id}
							bind:value={refundAmount}
							inputmode="decimal"
							dir="ltr"
							aria-invalid={invalid || undefined}
							aria-describedby={describedBy}
						/>
					{/snippet}
				</FormField>
				<FormField label={m().common.reason} id="refund-reason" error={refundForm.errors.reason}>
					{#snippet children({ id, invalid })}
						<Textarea {id} bind:value={refundReason} rows={3} aria-invalid={invalid || undefined} />
					{/snippet}
				</FormField>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (refundFor = null)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={refundForm.pending}
					>{#if refundForm.pending}<Spinner data-icon="inline-start" />{/if}{m().common
						.submit}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root open={!!reviewFor} onOpenChange={(o) => !o && (reviewFor = null)}>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={submitReview}>
			<Dialog.Header>
				<Dialog.Title>{m().orders.review}</Dialog.Title>
				<Dialog.Description><bdi>{reviewFor?.store_name}</bdi></Dialog.Description>
			</Dialog.Header>
			<Field.Group>
				<StarInput bind:value={rating} label={m().orders.rating} />
				<FormField
					label={m().orders.comment}
					id="review-comment"
					error={reviewForm.errors.comment}
					optional
				>
					{#snippet children({ id })}<Textarea
							{id}
							bind:value={comment}
							rows={4}
							maxlength={3000}
						/>{/snippet}
				</FormField>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (reviewFor = null)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={reviewForm.pending}
					>{#if reviewForm.pending}<Spinner data-icon="inline-start" />{/if}{m().common
						.submit}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
