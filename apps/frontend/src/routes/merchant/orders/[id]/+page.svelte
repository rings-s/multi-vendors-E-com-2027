<script lang="ts">
	import { isolate } from '#lib/i18n/bidi.js';
	import { invalidate } from '$app/navigation';
	import BanIcon from '@lucide/svelte/icons/ban';
	import CheckIcon from '@lucide/svelte/icons/check';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';
	import TruckIcon from '@lucide/svelte/icons/truck';
	import Undo2Icon from '@lucide/svelte/icons/undo-2';
	import XIcon from '@lucide/svelte/icons/x';
	import { api, call } from '#lib/api/client.js';
	import type { DeliveryStatusUpdate } from '#lib/api/types.js';
	import DeliveryCard from '#lib/components/app/DeliveryCard.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import OrderItemsTable from '#lib/components/app/OrderItemsTable.svelte';
	import OrderSummary from '#lib/components/app/OrderSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import TestModeBadge from '#lib/components/app/TestModeBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as RadioGroup from '#lib/components/ui/radio-group/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { confirm, prompt } from '#lib/confirm.svelte.js';
	import { sarToHalalas } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	type RefundScope = 'AUTO' | 'ITEMS' | 'DELIVERY';
	type Next = 'ACCEPTED' | 'PROCESSING' | 'SHIPPED' | 'DELIVERED' | 'COMPLETED';
	const PHYSICAL: Record<string, Next[]> = {
		PAID: ['ACCEPTED'],
		ACCEPTED: ['PROCESSING', 'SHIPPED'],
		PROCESSING: ['SHIPPED'],
		SHIPPED: ['DELIVERED']
	};
	const SERVICE: Record<string, Next[]> = {
		PAID: ['ACCEPTED'],
		ACCEPTED: ['PROCESSING', 'COMPLETED'],
		PROCESSING: ['COMPLETED']
	};

	let { data }: PageProps = $props();
	const o = $derived(data.order);
	const delivery = $derived(o.delivery);
	// Physical orders with a delivery are driven by the delivery's own status machine.
	const flow = $derived(
		delivery ? [] : ((o.fulfillment_type === 'SERVICE' ? SERVICE : PHYSICAL)[o.status] ?? [])
	);
	const address = $derived(delivery ? null : (o.delivery_address as Record<string, string> | null));
	const pickup = $derived(delivery?.method === 'PICKUP');
	const refundable = $derived(
		!!o.payment && ['PAID', 'PARTIALLY_REFUNDED'].includes(o.payment.status)
	);
	const cancellable = $derived(
		['PAID', 'ACCEPTED', 'PROCESSING'].includes(o.status) ||
			(delivery?.status === 'FAILED' && o.status === 'SHIPPED')
	);
	let busy = $state(false);
	const refresh = () => invalidate('app:merchant-order');

	const label: Record<Next, () => string> = {
		ACCEPTED: () => m().merchant.accept,
		PROCESSING: () => m().merchant.markProcessing,
		SHIPPED: () => m().merchant.markShipped,
		DELIVERED: () => m().merchant.markDelivered,
		COMPLETED: () => m().merchant.markCompleted
	};

	async function run<T>(fn: () => Promise<T>, success = m().merchant.fulfillmentUpdated) {
		busy = true;
		const ok = await action(fn, success);
		busy = false;
		if (ok) await refresh();
		return ok;
	}

	async function advance(status: Next) {
		if (status === 'SHIPPED') return openShip();
		await run(() =>
			call(
				api.POST('/api/v1/merchant/orders/{mo_id}/fulfillment', {
					params: { path: { mo_id: o.id } },
					body: { status }
				})
			)
		);
	}

	async function reject() {
		const reason = await prompt({
			title: m().merchant.reject,
			label: m().merchant.rejectReason,
			minLength: 3,
			destructive: true,
			confirmLabel: m().merchant.reject
		});
		if (reason)
			await run(() =>
				call(
					api.POST('/api/v1/merchant/orders/{mo_id}/reject', {
						params: { path: { mo_id: o.id } },
						body: { reason }
					})
				)
			);
	}

	async function cancelOrder() {
		const reason = await prompt({
			title: m().merchant.cancelOrder,
			label: m().merchant.cancelReason,
			minLength: 3,
			destructive: true,
			confirmLabel: m().merchant.cancelOrder
		});
		if (reason)
			await run(() =>
				call(
					api.POST('/api/v1/merchant/orders/{mo_id}/cancel', {
						params: { path: { mo_id: o.id } },
						body: { reason }
					})
				)
			);
	}

	async function decideCancellation(approve: boolean) {
		if (approve && !(await confirm({ title: m().merchant.approveCancellation, destructive: true })))
			return;
		await run(() =>
			call(
				api.POST('/api/v1/merchant/orders/{mo_id}/cancellation-decision', {
					params: { path: { mo_id: o.id } },
					body: { approve, note: null }
				})
			)
		);
	}

	// Delivery status changes
	type DeliveryNext = DeliveryStatusUpdate['status'];
	function deliveryLabel(next: string): string {
		const failed = delivery?.status === 'FAILED';
		if (next === 'OUT_FOR_DELIVERY' && failed) return m().delivery.sendAgain;
		if (next === 'READY_FOR_PICKUP' && failed) return m().delivery.readyAgain;
		if (next === 'DELIVERED' && pickup) return m().delivery.markCollected;
		if (next === 'FAILED' && pickup) return m().delivery.markNotCollected;
		return m().delivery.action[next as DeliveryNext] ?? next;
	}
	async function updateDelivery(body: DeliveryStatusUpdate) {
		return run(
			() =>
				call(
					api.POST('/api/v1/merchant/orders/{mo_id}/delivery/status', {
						params: { path: { mo_id: o.id } },
						body
					})
				),
			m().delivery.updated
		);
	}
	function advanceDelivery(next: DeliveryNext) {
		if (next === 'FAILED') {
			failReason = '';
			failForm.reset();
			failOpen = true;
		} else if (next === 'OUT_FOR_DELIVERY') {
			openShip();
		} else {
			void updateDelivery({ status: next, note: null, failure_reason: null });
		}
	}

	let failOpen = $state(false);
	let failReason = $state('');
	const failForm = new FormState();
	async function submitFail(e: SubmitEvent) {
		e.preventDefault();
		failForm.reset();
		if (failReason.trim().length < 3)
			return failForm.fail('failure_reason', m().errors.codes.reason_required);
		if (await updateDelivery({ status: 'FAILED', failure_reason: failReason.trim(), note: null }))
			failOpen = false;
	}

	// Ship dialog
	let shipOpen = $state(false);
	let ship = $state({ carrier: '', tracking_number: '', tracking_url: '', note: '' });
	function openShip() {
		ship = { carrier: '', tracking_number: '', tracking_url: '', note: '' };
		shipOpen = true;
	}
	async function submitShip(e: SubmitEvent) {
		e.preventDefault();
		if (delivery) {
			const done = await updateDelivery({
				status: 'OUT_FOR_DELIVERY',
				carrier: ship.carrier || null,
				tracking_number: ship.tracking_number || null,
				tracking_url: ship.tracking_url || null,
				note: ship.note || null,
				failure_reason: null
			});
			if (done) shipOpen = false;
			return;
		}
		const ok = await run(() =>
			call(
				api.POST('/api/v1/merchant/orders/{mo_id}/fulfillment', {
					params: { path: { mo_id: o.id } },
					body: {
						status: 'SHIPPED',
						carrier: ship.carrier || null,
						tracking_number: ship.tracking_number || null,
						tracking_url: ship.tracking_url || null,
						note: ship.note || null
					}
				})
			)
		);
		if (ok) shipOpen = false;
	}

	// Refund dialog
	let refundOpen = $state(false);
	let refund = $state<{ amount: string; reason: string; restock: boolean; scope: RefundScope }>({
		amount: '',
		reason: '',
		restock: false,
		scope: 'AUTO'
	});
	const refundForm = new FormState();
	async function submitRefund(e: SubmitEvent) {
		e.preventDefault();
		refundForm.reset();
		const amount = refund.amount.trim() ? sarToHalalas(refund.amount) : null;
		if (refund.amount.trim() && !amount) return refundForm.fail('amount', m().errors.invalidAmount);
		if (refund.reason.trim().length < 3)
			return refundForm.fail('reason', m().errors.codes.reason_required);
		const res = await refundForm.submit(
			() =>
				call(
					api.POST('/api/v1/merchant/orders/{mo_id}/refunds', {
						params: { path: { mo_id: o.id } },
						body: {
							amount,
							reason: refund.reason.trim(),
							restock: refund.scope !== 'DELIVERY' && refund.restock,
							scope: refund.scope
						}
					})
				),
			{ success: m().merchant.fulfillmentUpdated }
		);
		if (res.ok) {
			refundOpen = false;
			await refresh();
		}
	}
</script>

<svelte:head
	><title>{m().orders.storeOrder({ number: isolate(o.number) })} · {m().brand.name}</title
	></svelte:head
>

<div class="flex flex-col gap-8">
	<PageHeader title={m().orders.storeOrder({ number: isolate(o.number) })}>
		{#snippet meta()}
			<div class="flex flex-wrap items-center gap-3 text-sm text-ink-3">
				<StatusBadge status={o.status} />
				<span>{fmt.datetime(o.created_at)}</span>
				{#if o.payment?.is_test}<TestModeBadge />{/if}
			</div>
		{/snippet}
		{#snippet actions()}
			{#each flow as next (next)}
				<Button onclick={() => advance(next)} disabled={busy} data-testid="advance-{next}">
					{#if next === 'SHIPPED'}<TruckIcon data-icon="inline-start" />{:else}<CheckIcon
							data-icon="inline-start"
						/>{/if}{label[next]()}
				</Button>
			{/each}
			{#if delivery}
				{#each delivery.next_statuses ?? [] as next (next)}
					<Button
						variant={next === 'FAILED' ? 'outline' : 'default'}
						onclick={() => advanceDelivery(next as DeliveryNext)}
						disabled={busy}
						data-testid="delivery-{next}"
					>
						{#if next === 'OUT_FOR_DELIVERY'}<TruckIcon
								data-icon="inline-start"
							/>{:else if next === 'FAILED'}<TriangleAlertIcon
								data-icon="inline-start"
							/>{:else}<CheckIcon data-icon="inline-start" />{/if}{deliveryLabel(next)}
					</Button>
				{/each}
			{/if}
			{#if o.status === 'PAID'}
				<Button variant="outline" onclick={reject} disabled={busy}
					><XIcon data-icon="inline-start" />{m().merchant.reject}</Button
				>
			{:else if cancellable && o.cancellation_status !== 'REQUESTED'}
				<Button variant="outline" onclick={cancelOrder} disabled={busy}
					><BanIcon data-icon="inline-start" />{m().merchant.cancelOrder}</Button
				>
			{/if}
			{#if refundable}
				<Button
					variant="outline"
					onclick={() => {
						refund = { amount: '', reason: '', restock: false, scope: 'AUTO' };
						refundForm.reset();
						refundOpen = true;
					}}
					disabled={busy}><Undo2Icon data-icon="inline-start" />{m().merchant.issueRefund}</Button
				>
			{/if}
		{/snippet}
	</PageHeader>

	{#if o.cancellation_status === 'REQUESTED'}
		<Alert.Root variant="warning">
			<Alert.Title>{m().merchant.cancellationRequest}</Alert.Title>
			<Alert.Description>
				{#if o.cancellation_reason}<p>{o.cancellation_reason}</p>{/if}
				<div class="mt-3 flex gap-2">
					<Button
						size="sm"
						variant="destructive"
						onclick={() => decideCancellation(true)}
						disabled={busy}>{m().merchant.approveCancellation}</Button
					>
					<Button
						size="sm"
						variant="outline"
						onclick={() => decideCancellation(false)}
						disabled={busy}>{m().merchant.declineCancellation}</Button
					>
				</div>
			</Alert.Description>
		</Alert.Root>
	{/if}

	<div class="grid gap-8 lg:grid-cols-[1fr_20rem]">
		<div class="flex flex-col gap-6">
			<section class="overflow-hidden rounded-2xl border border-line bg-surface">
				<OrderItemsTable items={o.items} />
			</section>
			{#if delivery}
				<DeliveryCard {delivery} showTerms />
			{/if}
			{#if o.shipments.length}
				<section>
					<Card.Root class="h-full">
						<Card.Header>
							<Card.Title role="heading" aria-level={2}>{m().orders.shipment}</Card.Title>
						</Card.Header>
						<Card.Content>
							<Item.Group class="gap-0">
								{#each o.shipments as s, i (s.id)}
									{#if i > 0}<Item.Separator class="my-0" />{/if}
									<Item.Root role="listitem" size="sm" class="px-0">
										<Item.Content>
											<Item.Title class="font-normal"
												>{s.carrier}{#if s.tracking_number}
													· <span dir="ltr" class="tabular">{s.tracking_number}</span
													>{/if}</Item.Title
											>
										</Item.Content>
										<Item.Actions><StatusBadge status={s.status} /></Item.Actions>
									</Item.Root>
								{/each}
							</Item.Group>
						</Card.Content>
					</Card.Root>
				</section>
			{/if}
			{#if o.merchant_note}
				<Alert.Root role="note">
					<Alert.Title>{m().common.note}</Alert.Title>
					<Alert.Description>{o.merchant_note}</Alert.Description>
				</Alert.Root>
			{/if}
		</div>

		<aside class="h-fit">
			<Card.Root class="h-full">
				<Card.Content class="flex flex-col gap-6 text-sm">
					<OrderSummary
						subtotal={o.items_subtotal}
						discount={o.discount_total}
						delivery={o.delivery_fee}
						deliveryMethod={o.delivery_method}
						vat={o.vat_total}
						total={o.total}
					>
						<Separator class="my-0.5" />
						<div class="flex justify-between gap-4">
							<dt class="text-ink-2">{m().delivery.itemCommission}</dt>
							<dd>−{fmt.money(o.commission_total)}</dd>
						</div>
						{#if o.delivery_commission}
							<div class="flex justify-between gap-4">
								<dt class="text-ink-2">{m().delivery.deliveryCommission}</dt>
								<dd>−{fmt.money(o.delivery_commission)}</dd>
							</div>
						{/if}
						<div class="flex justify-between gap-4 font-medium">
							<dt>{m().merchant.net}</dt>
							<dd data-testid="merchant-net">{fmt.money(o.merchant_net)}</dd>
						</div>
						{#if o.merchant_delivery_share}
							<div class="flex justify-between gap-4 text-ink-3">
								<dt>{m().delivery.deliveryEarnings}</dt>
								<dd>{fmt.money(o.merchant_delivery_share)}</dd>
							</div>
						{/if}
						{#if o.refunded_amount}<div class="flex justify-between gap-4 text-danger">
								<dt>{m().orders.refunded}</dt>
								<dd>{fmt.money(o.refunded_amount)}</dd>
							</div>{/if}
					</OrderSummary>
					{#if o.payment}
						<div class="flex flex-col gap-1">
							<p class="text-ink-3">{m().orders.payment}</p>
							<StatusBadge status={o.payment.status} />
						</div>
					{/if}
					<div class="flex flex-col gap-1">
						<p class="text-ink-3">{m().merchant.customer}</p>
						<p class="font-medium"><bdi>{o.customer_name}</bdi></p>
						<p dir="ltr" class="text-start tabular">{fmt.phone(o.customer_phone)}</p>
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

<Dialog.Root bind:open={shipOpen}>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={submitShip}>
			<Dialog.Header>
				<Dialog.Title
					>{delivery ? m().delivery.dispatchTitle : m().merchant.markShipped}</Dialog.Title
				>
				{#if delivery}<Dialog.Description>{m().delivery.dispatchHint}</Dialog.Description>{/if}
			</Dialog.Header>
			<Field.Group>
				<FormField label={m().orders.carrier} id="sh-carrier" optional
					>{#snippet children({ id })}<Input {id} bind:value={ship.carrier} />{/snippet}</FormField
				>
				<FormField label={m().orders.trackingNumber} id="sh-num" optional
					>{#snippet children({ id })}<Input
							{id}
							dir="ltr"
							bind:value={ship.tracking_number}
						/>{/snippet}</FormField
				>
				<FormField label={m().orders.tracking} id="sh-url" optional
					>{#snippet children({ id })}<Input
							{id}
							type="url"
							dir="ltr"
							placeholder="https://"
							bind:value={ship.tracking_url}
						/>{/snippet}</FormField
				>
				<FormField label={m().common.note} id="sh-note" optional
					>{#snippet children({ id })}<Textarea
							{id}
							rows={2}
							bind:value={ship.note}
						/>{/snippet}</FormField
				>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (shipOpen = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={busy}
					>{#if busy}<Spinner data-icon="inline-start" />{/if}{delivery
						? m().delivery.action.OUT_FOR_DELIVERY
						: m().merchant.markShipped}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={refundOpen}>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={submitRefund} novalidate>
			<Dialog.Header>
				<Dialog.Title>{m().merchant.issueRefund}</Dialog.Title>
				<Dialog.Description
					>{fmt.money(o.total)}{#if o.refunded_amount}
						· {m().orders.refunded}: {fmt.money(o.refunded_amount)}{/if}</Dialog.Description
				>
			</Dialog.Header>
			<Field.Group>
				{#if o.delivery_fee > 0}
					<Field.Set>
						<Field.Legend variant="label">{m().delivery.refundScope}</Field.Legend>
						<RadioGroup.Root bind:value={refund.scope}>
							{#each ['AUTO', 'ITEMS', 'DELIVERY'] as const as scope (scope)}
								<Field.Field orientation="horizontal">
									<RadioGroup.Item value={scope} id="rf-scope-{scope}" />
									<Field.Label for="rf-scope-{scope}" class="font-normal"
										>{m().delivery.scope[scope]}</Field.Label
									>
								</Field.Field>
							{/each}
						</RadioGroup.Root>
					</Field.Set>
				{/if}
				<FormField
					label={m().orders.refundAmount}
					id="rf-amount"
					hint={m().merchant.refundAmountHint}
					error={refundForm.errors.amount}
					optional
				>
					{#snippet children({ id, invalid, describedBy })}<Input
							{id}
							inputmode="decimal"
							dir="ltr"
							bind:value={refund.amount}
							aria-invalid={invalid || undefined}
							aria-describedby={describedBy}
						/>{/snippet}
				</FormField>
				<FormField label={m().common.reason} id="rf-reason" error={refundForm.errors.reason}>
					{#snippet children({ id, invalid })}<Textarea
							{id}
							rows={3}
							bind:value={refund.reason}
							aria-invalid={invalid || undefined}
						/>{/snippet}
				</FormField>
				{#if o.fulfillment_type !== 'SERVICE' && refund.scope !== 'DELIVERY'}
					<Field.Field orientation="horizontal">
						<Checkbox id="rf-restock" bind:checked={refund.restock} /><Field.Label
							for="rf-restock"
							class="font-normal">{m().merchant.restock}</Field.Label
						>
					</Field.Field>
				{/if}
				{#if refundForm.message}<Alert.Root variant="destructive"
						><Alert.Description>{refundForm.message}</Alert.Description></Alert.Root
					>{/if}
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (refundOpen = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" variant="destructive" disabled={refundForm.pending}
					>{#if refundForm.pending}<Spinner data-icon="inline-start" />{/if}{m().merchant
						.issueRefund}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={failOpen}>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={submitFail} novalidate>
			<Dialog.Header>
				<Dialog.Title
					>{pickup ? m().delivery.markNotCollected : m().delivery.failTitle}</Dialog.Title
				>
				<Dialog.Description>{m().delivery.failHint}</Dialog.Description>
			</Dialog.Header>
			<FormField
				label={m().delivery.failureReason}
				id="df-reason"
				error={failForm.errors.failure_reason}
			>
				{#snippet children({ id, invalid })}<Textarea
						{id}
						rows={3}
						bind:value={failReason}
						aria-invalid={invalid || undefined}
					/>{/snippet}
			</FormField>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (failOpen = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" variant="destructive" disabled={busy}
					>{#if busy}<Spinner data-icon="inline-start" />{/if}{deliveryLabel('FAILED')}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
