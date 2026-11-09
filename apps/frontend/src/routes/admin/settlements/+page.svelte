<script lang="ts">
	import { invalidate } from '$app/navigation';
	import LandmarkIcon from '@lucide/svelte/icons/landmark';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { api, call } from '#lib/api/client.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { sarToHalalas } from '#lib/format.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	let open = $state(false);
	const form = new FormState();
	let v = $state({
		merchant_id: '',
		amount: '',
		provider_settlement_id: '',
		completed_at: '',
		evidence_reference: ''
	});

	async function record(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const amount = sarToHalalas(v.amount);
		if (!amount) return form.fail('amount', m().errors.invalidAmount);
		if (!v.completed_at) return form.fail('completed_at', m().common.required);
		const res = await form.submit(
			() =>
				call(
					api.POST('/api/v1/admin/settlements/reconciled', {
						body: { ...v, amount, completed_at: new Date(v.completed_at).toISOString() }
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) {
			open = false;
			await invalidate('app:admin-settlements');
		}
	}
</script>

<svelte:head><title>{t.settlements} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.settlements}>
		{#snippet actions()}<Button
				variant="outline"
				onclick={() => {
					form.reset();
					open = true;
				}}><PlusIcon data-icon="inline-start" />{t.recordSettlement}</Button
			>{/snippet}
	</PageHeader>
	<FilterBar>
		<Field.Field class="w-72">
			<Field.Label for="as-mer">{t.merchantId}</Field.Label><Input
				id="as-mer"
				name="merchant_id"
				dir="ltr"
				value={data.filters.merchant_id}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="as-status">{m().common.status}</Field.Label>
			<NativeSelect.Root id="as-status" name="status" value={data.filters.status}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				{#each ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'] as s (s)}<NativeSelect.Option
						value={s}>{statusLabel(s)}</NativeSelect.Option
					>{/each}
			</NativeSelect.Root>
		</Field.Field>
	</FilterBar>
	{#if data.settlements.items.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{t.settlementId}</Table.Head>
						<Table.Head>{t.merchants}</Table.Head>
						<Table.Head>{t.completedAt}</Table.Head>
						<Table.Head>{m().merchant.confirmationSource}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
						<Table.Head class="text-end">{m().common.amount}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.settlements.items as s (s.id)}
						<Table.Row>
							<Table.Cell dir="ltr" class="text-start tabular"
								>{s.provider_settlement_id}{#if s.is_test}<Badge variant="warning" class="ms-1.5"
										>{m().common.testMode}</Badge
									>{/if}</Table.Cell
							>
							<Table.Cell
								><a
									href="/admin/merchants/{s.merchant_id}"
									class="text-primary hover:underline"
									dir="ltr">{s.merchant_id.slice(0, 8)}</a
								></Table.Cell
							>
							<Table.Cell class="text-ink-3">{fmt.datetime(s.completed_at)}</Table.Cell>
							<Table.Cell
								>{s.confirmation_source
									? statusLabel(s.confirmation_source)
									: '—'}{#if s.confirmation_reference}<p class="text-xs text-ink-3" dir="ltr">
										{s.confirmation_reference}
									</p>{/if}</Table.Cell
							>
							<Table.Cell><StatusBadge status={s.status} /></Table.Cell>
							<Table.Cell class="text-end font-medium tabular">{fmt.money(s.amount)}</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={data.settlements.total}
			page={data.settlements.page}
			pageSize={data.settlements.page_size}
		/>
	{:else}
		<EmptyState icon={LandmarkIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>

<Dialog.Root bind:open>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={record} novalidate>
			<Dialog.Header><Dialog.Title>{t.recordSettlement}</Dialog.Title></Dialog.Header>
			<Field.Group>
				<Alert.Root><Alert.Description>{t.settlementNote}</Alert.Description></Alert.Root>
				{#if form.message}<Alert.Root variant="destructive"
						><Alert.Description>{form.message}</Alert.Description></Alert.Root
					>{/if}
				<FormField label={t.merchantId} id="rs-mer" error={form.errors.merchant_id}
					>{#snippet children({ id })}<Input
							{id}
							dir="ltr"
							bind:value={v.merchant_id}
						/>{/snippet}</FormField
				>
				<FormField label={m().orders.refundAmount} id="rs-amount" error={form.errors.amount}
					>{#snippet children({ id })}<Input
							{id}
							dir="ltr"
							inputmode="decimal"
							bind:value={v.amount}
						/>{/snippet}</FormField
				>
				<FormField label={t.settlementId} id="rs-sid" error={form.errors.provider_settlement_id}
					>{#snippet children({ id })}<Input
							{id}
							dir="ltr"
							bind:value={v.provider_settlement_id}
						/>{/snippet}</FormField
				>
				<FormField label={t.completedAt} id="rs-at" error={form.errors.completed_at}
					>{#snippet children({ id })}<Input
							{id}
							type="datetime-local"
							bind:value={v.completed_at}
						/>{/snippet}</FormField
				>
				<FormField label={t.evidence} id="rs-ev" error={form.errors.evidence_reference}
					>{#snippet children({ id })}<Input
							{id}
							bind:value={v.evidence_reference}
						/>{/snippet}</FormField
				>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (open = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().common.save}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
