<script lang="ts">
	import { invalidate } from '$app/navigation';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import ShieldAlertIcon from '@lucide/svelte/icons/shield-alert';
	import { api, call } from '#lib/api/client.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { sarToHalalas } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	const refresh = () => invalidate('app:chargebacks');

	async function resolve(id: string, outcome: 'WON' | 'LOST') {
		if (
			!(await confirm({
				title: `${outcome === 'WON' ? t.resolveWon : t.resolveLost}?`,
				destructive: outcome === 'LOST'
			}))
		)
			return;
		await action(
			() =>
				call(
					api.POST('/api/v1/admin/chargebacks/{chargeback_id}/resolve', {
						params: { path: { chargeback_id: id } },
						body: { outcome }
					})
				),
			m().common.saved
		);
		await refresh();
	}

	let open = $state(false);
	let v = $state({ payment_id: '', amount: '', provider_reference: '', reason: '' });
	const form = new FormState();
	async function create(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const amount = sarToHalalas(v.amount);
		if (!amount) return form.fail('amount', m().errors.invalidAmount);
		const res = await form.submit(
			() => call(api.POST('/api/v1/admin/chargebacks', { body: { ...v, amount } })),
			{ success: m().common.saved }
		);
		if (res.ok) {
			open = false;
			await refresh();
		}
	}
</script>

<svelte:head><title>{t.chargebacks} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.chargebacks}>
		{#snippet actions()}<Button
				variant="outline"
				onclick={() => {
					v = { payment_id: '', amount: '', provider_reference: '', reason: '' };
					form.reset();
					open = true;
				}}><PlusIcon data-icon="inline-start" />{t.openChargeback}</Button
			>{/snippet}
	</PageHeader>
	{#if data.chargebacks.items.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{t.reference}</Table.Head>
						<Table.Head>{m().common.date}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
						<Table.Head class="text-end">{m().common.amount}</Table.Head>
						<Table.Head class="text-end">{t.merchants}</Table.Head>
						<Table.Head class="text-end">{m().status.PLATFORM}</Table.Head>
						<Table.Head><span class="sr-only">{m().common.actions}</span></Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.chargebacks.items as c (c.id)}
						<Table.Row>
							<Table.Cell
								><a href="/admin/payments/{c.payment_id}" class="tabular hover:underline" dir="ltr"
									>{c.provider_reference}</a
								>{#if c.reason}<p class="text-xs text-ink-3">
										<bdi>{c.reason}</bdi>
									</p>{/if}</Table.Cell
							>
							<Table.Cell class="text-ink-3">{fmt.date(c.opened_at)}</Table.Cell>
							<Table.Cell><StatusBadge status={c.status} /></Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(c.amount)}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(c.merchant_portion)}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(c.platform_portion)}</Table.Cell>
							<Table.Cell class="text-end">
								{#if c.status === 'OPEN'}
									<div class="flex justify-end gap-1">
										<Button size="sm" variant="outline" onclick={() => resolve(c.id, 'WON')}
											>{t.resolveWon}</Button
										>
										<Button
											size="sm"
											variant="ghost"
											class="text-danger"
											onclick={() => resolve(c.id, 'LOST')}>{t.resolveLost}</Button
										>
									</div>
								{/if}
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={data.chargebacks.total}
			page={data.chargebacks.page}
			pageSize={data.chargebacks.page_size}
		/>
	{:else}
		<EmptyState icon={ShieldAlertIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>

<Dialog.Root bind:open>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={create} novalidate>
			<Dialog.Header><Dialog.Title>{t.openChargeback}</Dialog.Title></Dialog.Header>
			<Field.Group>
				{#if form.message}<Alert.Root variant="destructive"
						><Alert.Description>{form.message}</Alert.Description></Alert.Root
					>{/if}
				<FormField label={t.paymentId} id="cb-pid" error={form.errors.payment_id}
					>{#snippet children({ id })}<Input
							{id}
							dir="ltr"
							bind:value={v.payment_id}
						/>{/snippet}</FormField
				>
				<FormField label={m().orders.refundAmount} id="cb-amount" error={form.errors.amount}
					>{#snippet children({ id })}<Input
							{id}
							dir="ltr"
							inputmode="decimal"
							bind:value={v.amount}
						/>{/snippet}</FormField
				>
				<FormField label={t.reference} id="cb-ref" error={form.errors.provider_reference}
					>{#snippet children({ id })}<Input
							{id}
							dir="ltr"
							bind:value={v.provider_reference}
						/>{/snippet}</FormField
				>
				<FormField label={m().common.reason} id="cb-reason" optional
					>{#snippet children({ id })}<Textarea
							{id}
							rows={2}
							bind:value={v.reason}
						/>{/snippet}</FormField
				>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (open = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().common.create}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
