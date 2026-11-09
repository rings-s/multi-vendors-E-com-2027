<script lang="ts">
	import { invalidate } from '$app/navigation';
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
	import RefreshCwIcon from '@lucide/svelte/icons/refresh-cw';
	import Undo2Icon from '@lucide/svelte/icons/undo-2';
	import { api, call } from '#lib/api/client.js';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import TestModeBadge from '#lib/components/app/TestModeBadge.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Collapsible from '#lib/components/ui/collapsible/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { ScrollArea } from '#lib/components/ui/scroll-area/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { sarToHalalas } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const p = $derived(data.payment);
	const t = $derived(m().admin);
	let busy = $state(false);
	const refundable = $derived(['PAID', 'PARTIALLY_REFUNDED'].includes(p.status));

	async function sync() {
		busy = true;
		await action(
			() =>
				call(
					api.POST('/api/v1/admin/payments/{payment_id}/sync', {
						params: { path: { payment_id: p.id } }
					})
				),
			m().merchant.synced
		);
		busy = false;
		await invalidate('app:admin-payment');
	}

	let open = $state(false);
	let amount = $state('');
	let reason = $state('');
	let scope = $state<'AUTO' | 'ITEMS' | 'DELIVERY'>('AUTO');
	const hasDelivery = $derived(p.allocations.some((a) => a.delivery_amount > 0));
	const form = new FormState();
	async function refund(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const a = amount.trim() ? sarToHalalas(amount) : null;
		if (amount.trim() && !a) return form.fail('amount', m().errors.invalidAmount);
		if (reason.trim().length < 3) return form.fail('reason', m().errors.codes.reason_required);
		const res = await form.submit(
			() =>
				call(
					api.POST('/api/v1/admin/payments/{payment_id}/refunds', {
						params: { path: { payment_id: p.id } },
						body: { amount: a, reason: reason.trim(), restock: false, scope }
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) {
			open = false;
			await invalidate('app:admin-payment');
		}
	}
</script>

<svelte:head><title>{t.payments} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={fmt.money(p.amount)} description={p.provider_payment_id ?? p.id}>
		{#snippet meta()}<div class="flex flex-wrap items-center gap-3">
				<StatusBadge status={p.status} />{#if p.is_test}<TestModeBadge />{/if}<a
					class="text-sm text-primary hover:underline"
					href="/admin/orders/{p.order_id}">{m().checkout.viewOrder}</a
				>
			</div>{/snippet}
		{#snippet actions()}
			<Button variant="outline" onclick={sync} disabled={busy}
				>{#if busy}<Spinner data-icon="inline-start" />{:else}<RefreshCwIcon
						data-icon="inline-start"
					/>{/if}{t.syncPayment}</Button
			>
			{#if refundable}<Button
					variant="destructive"
					onclick={() => {
						amount = '';
						reason = '';
						form.reset();
						open = true;
					}}><Undo2Icon data-icon="inline-start" />{t.refundPayment}</Button
				>{/if}
		{/snippet}
	</PageHeader>

	<Card.Root>
		<Card.Content>
			<dl class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				<div>
					<dt class="text-ink-3">{m().merchant.provider}</dt>
					<dd class="capitalize">{p.provider}</dd>
				</div>
				<div>
					<dt class="text-ink-3">{m().checkout.paymentMethod}</dt>
					<dd>{p.payment_method ?? '—'}</dd>
				</div>
				<div>
					<dt class="text-ink-3">{m().merchant.fee}</dt>
					<dd class="tabular">
						{p.fee == null ? '—' : fmt.money(p.fee)} · {statusLabel(p.fee_bearer)}
					</dd>
				</div>
				<div>
					<dt class="text-ink-3">{m().orders.refunded}</dt>
					<dd class="tabular">{fmt.money(p.refunded_amount)}</dd>
				</div>
				<div>
					<dt class="text-ink-3">{m().common.date}</dt>
					<dd>{fmt.datetime(p.created_at)}</dd>
				</div>
				<div>
					<dt class="text-ink-3">{m().checkout.paid}</dt>
					<dd>{fmt.datetime(p.paid_at)}</dd>
				</div>
				<div>
					<dt class="text-ink-3">{m().merchant.lastSynced}</dt>
					<dd>{fmt.datetime(p.last_synced_at)}</dd>
				</div>
				{#if p.failure_reason}<div>
						<dt class="text-ink-3">{m().common.reason}</dt>
						<dd class="text-danger">{p.failure_reason}</dd>
					</div>{/if}
			</dl>
		</Card.Content>
	</Card.Root>

	<section class="flex flex-col gap-3">
		<h2 class="type-title">{t.allocations}</h2>
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{t.recipient}</Table.Head>
						<Table.Head>ID</Table.Head>
						<Table.Head>{t.feeSource}</Table.Head>
						<Table.Head>{t.refundable}</Table.Head>
						<Table.Head class="text-end">{m().delivery.title}</Table.Head>
						<Table.Head class="text-end">{m().common.amount}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each p.allocations as a, i (i)}
						<Table.Row>
							<Table.Cell>{statusLabel(a.recipient_type)}</Table.Cell>
							<Table.Cell class="text-ink-2 tabular" dir="ltr">{a.recipient_id}</Table.Cell>
							<Table.Cell>{a.is_fee_source ? m().common.yes : m().common.no}</Table.Cell>
							<Table.Cell>{a.refundable ? m().common.yes : m().common.no}</Table.Cell>
							<Table.Cell class="text-end text-ink-2 tabular"
								>{fmt.money(a.delivery_amount)}</Table.Cell
							>
							<Table.Cell class="text-end font-medium tabular">{fmt.money(a.amount)}</Table.Cell>
						</Table.Row>
					{/each}
					<Table.Row>
						<Table.Cell colspan={5} class="font-medium">{m().common.total}</Table.Cell>
						<Table.Cell class="text-end font-medium tabular" data-testid="allocation-total"
							>{fmt.money(p.allocations.reduce((s, a) => s + a.amount, 0))}</Table.Cell
						>
					</Table.Row>
				</Table.Body>
			</Table.Root>
		</div>
	</section>

	{#if p.provider_response}
		<Collapsible.Root>
			<Card.Root>
				<Card.Header>
					<Card.Title role="heading" aria-level={2}>{t.providerResponse}</Card.Title>
					<Card.Action>
						<Collapsible.Trigger>
							{#snippet child({ props })}
								<Button
									{...props}
									variant="ghost"
									size="icon-sm"
									class="group"
									aria-label={t.providerResponse}
									><ChevronDownIcon
										class="transition-transform group-data-[state=open]:rotate-180"
									/></Button
								>
							{/snippet}
						</Collapsible.Trigger>
					</Card.Action>
				</Card.Header>
				<Collapsible.Content>
					<Card.Content>
						<ScrollArea class="max-h-96 rounded-lg bg-surface-2" dir="ltr">
							<pre class="p-4 text-xs">{JSON.stringify(p.provider_response, null, 2)}</pre>
						</ScrollArea>
					</Card.Content>
				</Collapsible.Content>
			</Card.Root>
		</Collapsible.Root>
	{/if}
</div>

<Dialog.Root bind:open>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={refund} novalidate>
			<Dialog.Header
				><Dialog.Title>{t.refundPayment}</Dialog.Title><Dialog.Description
					>{fmt.money(p.amount - p.refunded_amount)}</Dialog.Description
				></Dialog.Header
			>
			<Field.Group>
				{#if hasDelivery}
					<FormField label={m().delivery.refundScope} id="ar-scope">
						{#snippet children({ id })}
							<NativeSelect.Root {id} bind:value={scope} class="w-full">
								{#each ['AUTO', 'ITEMS', 'DELIVERY'] as const as sc (sc)}
									<NativeSelect.Option value={sc}>{m().delivery.scope[sc]}</NativeSelect.Option>
								{/each}
							</NativeSelect.Root>
						{/snippet}
					</FormField>
				{/if}
				<FormField
					label={m().orders.refundAmount}
					id="ar-amount"
					hint={m().merchant.refundAmountHint}
					error={form.errors.amount}
					optional
				>
					{#snippet children({ id, describedBy })}<Input
							{id}
							inputmode="decimal"
							dir="ltr"
							bind:value={amount}
							aria-describedby={describedBy}
						/>{/snippet}
				</FormField>
				<FormField label={m().common.reason} id="ar-reason" error={form.errors.reason}
					>{#snippet children({ id })}<Textarea
							{id}
							rows={3}
							bind:value={reason}
						/>{/snippet}</FormField
				>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (open = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" variant="destructive" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{t.refundPayment}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
