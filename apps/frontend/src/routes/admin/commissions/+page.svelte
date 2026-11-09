<script lang="ts">
	import { invalidate } from '$app/navigation';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { api, call } from '#lib/api/client.js';
	import type { CommissionRuleAdmin } from '#lib/api/types.js';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import QueryFilter from '#lib/components/app/QueryFilter.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { sarToHalalas } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m, pick, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	type Scope = 'GLOBAL' | 'CATEGORY' | 'MERCHANT';
	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	const now = Date.now();
	const isActive = (r: CommissionRuleAdmin) =>
		new Date(r.effective_from).getTime() <= now &&
		(!r.effective_to || new Date(r.effective_to).getTime() > now);
	const rate = (r: CommissionRuleAdmin) =>
		r.rate_type === 'FIXED' ? fmt.money(r.fixed_amount) : fmt.percent(r.rate);
	const catName = (id: string | null) => {
		const c = data.categories.find((x) => x.id === id);
		return c ? pick(c, 'name') : '';
	};

	async function end(r: CommissionRuleAdmin) {
		if (
			!(await confirm({
				title: t.endRule,
				description: t.endRuleConfirm,
				destructive: true,
				confirmLabel: t.endRule
			}))
		)
			return;
		await action(
			() =>
				call(
					api.POST('/api/v1/admin/commissions/{rule_id}/end', {
						params: { path: { rule_id: r.id } }
					})
				),
			m().common.saved
		);
		await invalidate('app:commissions');
	}

	let open = $state(false);
	const form = new FormState();
	let v = $state({
		scope: 'GLOBAL' as Scope,
		merchant_id: '',
		category_id: '',
		rate_type: 'PERCENTAGE' as 'PERCENTAGE' | 'FIXED',
		rate: '',
		fixed: '',
		effective_from: '',
		note: ''
	});
	async function create(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const fixed = v.rate_type === 'FIXED' ? sarToHalalas(v.fixed) : null;
		if (v.rate_type === 'FIXED' && fixed == null)
			return form.fail('fixed_amount', m().errors.invalidAmount);
		const res = await form.submit(
			() =>
				call(
					api.POST('/api/v1/admin/commissions', {
						body: {
							scope: v.scope,
							merchant_id: v.scope === 'MERCHANT' ? v.merchant_id : null,
							category_id: v.scope === 'CATEGORY' ? v.category_id : null,
							rate_type: v.rate_type,
							rate: v.rate_type === 'PERCENTAGE' ? v.rate : null,
							fixed_amount: fixed,
							effective_from: v.effective_from ? new Date(v.effective_from).toISOString() : null,
							note: v.note || null
						}
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) {
			open = false;
			await invalidate('app:commissions');
		}
	}
</script>

<svelte:head><title>{t.commissions} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.commissions}>
		{#snippet actions()}<Button
				onclick={() => {
					form.reset();
					open = true;
				}}><PlusIcon data-icon="inline-start" />{t.newRule}</Button
			>{/snippet}
	</PageHeader>
	<Alert.Root><Alert.Description>{t.commissionNote}</Alert.Description></Alert.Root>
	<QueryFilter
		param="scope"
		value={data.scope ?? ''}
		label={t.scope}
		options={['', 'GLOBAL', 'CATEGORY', 'MERCHANT'].map((s) => ({
			value: s,
			label: s ? statusLabel(s) : m().common.all
		}))}
	/>
	<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>{t.scope}</Table.Head>
					<Table.Head>{t.rateType}</Table.Head>
					<Table.Head class="text-end">{m().merchant.rate}</Table.Head>
					<Table.Head>{t.effectiveFrom}</Table.Head>
					<Table.Head>{t.effectiveTo}</Table.Head>
					<Table.Head>{m().common.status}</Table.Head>
					<Table.Head><span class="sr-only">{m().common.actions}</span></Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each data.rules.items as r (r.id)}
					<Table.Row>
						<Table.Cell>
							{statusLabel(r.scope)}
							{#if r.scope === 'CATEGORY'}<span class="text-ink-3">
									· {catName(r.category_id)}</span
								>{/if}
							{#if r.scope === 'MERCHANT'}<a
									href="/admin/merchants/{r.merchant_id}"
									class="block text-xs text-primary hover:underline"
									dir="ltr">{r.merchant_id?.slice(0, 8)}</a
								>{/if}
							{#if r.note}<p class="text-xs text-ink-3"><bdi>{r.note}</bdi></p>{/if}
						</Table.Cell>
						<Table.Cell>{statusLabel(r.rate_type)}</Table.Cell>
						<Table.Cell class="text-end font-medium tabular">{rate(r)}</Table.Cell>
						<Table.Cell class="text-ink-3">{fmt.datetime(r.effective_from)}</Table.Cell>
						<Table.Cell class="text-ink-3">{fmt.datetime(r.effective_to)}</Table.Cell>
						<Table.Cell
							><StatusBadge
								status={isActive(r) ? 'ACTIVE' : r.effective_to ? 'CLOSED' : 'PENDING'}
							/></Table.Cell
						>
						<Table.Cell class="text-end"
							>{#if !r.effective_to && r.scope !== 'GLOBAL'}<Button
									size="sm"
									variant="ghost"
									onclick={() => end(r)}>{t.endRule}</Button
								>{/if}</Table.Cell
						>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
	<Paginator total={data.rules.total} page={data.rules.page} pageSize={data.rules.page_size} />
</div>

<Dialog.Root bind:open>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={create} novalidate>
			<Dialog.Header
				><Dialog.Title>{t.newRule}</Dialog.Title><Dialog.Description
					>{t.commissionNote}</Dialog.Description
				></Dialog.Header
			>
			<Field.Group>
				{#if form.message}<Alert.Root variant="destructive"
						><Alert.Description>{form.message}</Alert.Description></Alert.Root
					>{/if}
				<div class="grid gap-4 sm:grid-cols-2">
					<FormField label={t.scope} id="cr-scope">
						{#snippet children({ id })}<NativeSelect.Root {id} bind:value={v.scope} class="w-full"
								>{#each ['GLOBAL', 'CATEGORY', 'MERCHANT'] as s (s)}<NativeSelect.Option value={s}
										>{statusLabel(s)}</NativeSelect.Option
									>{/each}</NativeSelect.Root
							>{/snippet}
					</FormField>
					{#if v.scope === 'MERCHANT'}
						<FormField label={t.merchantId} id="cr-mer" error={form.errors.merchant_id}
							>{#snippet children({ id })}<Input
									{id}
									dir="ltr"
									bind:value={v.merchant_id}
								/>{/snippet}</FormField
						>
					{:else if v.scope === 'CATEGORY'}
						<FormField label={m().stores.category} id="cr-cat" error={form.errors.category_id}>
							{#snippet children({ id })}<NativeSelect.Root
									{id}
									bind:value={v.category_id}
									class="w-full"
									><NativeSelect.Option value="">—</NativeSelect.Option
									>{#each data.categories as c (c.id)}<NativeSelect.Option value={c.id}
											>{pick(c, 'name')}</NativeSelect.Option
										>{/each}</NativeSelect.Root
								>{/snippet}
						</FormField>
					{/if}
					<FormField label={t.rateType} id="cr-type">
						{#snippet children({ id })}<NativeSelect.Root
								{id}
								bind:value={v.rate_type}
								class="w-full"
								><NativeSelect.Option value="PERCENTAGE">{t.percentage}</NativeSelect.Option
								><NativeSelect.Option value="FIXED">{t.fixed}</NativeSelect.Option
								></NativeSelect.Root
							>{/snippet}
					</FormField>
					{#if v.rate_type === 'PERCENTAGE'}
						<FormField label={t.ratePercent} id="cr-rate" error={form.errors.rate}
							>{#snippet children({ id })}<Input
									{id}
									dir="ltr"
									inputmode="decimal"
									bind:value={v.rate}
								/>{/snippet}</FormField
						>
					{:else}
						<FormField label={t.fixedAmount} id="cr-fixed" error={form.errors.fixed_amount}
							>{#snippet children({ id })}<Input
									{id}
									dir="ltr"
									inputmode="decimal"
									bind:value={v.fixed}
								/>{/snippet}</FormField
						>
					{/if}
					<FormField
						label={t.effectiveFrom}
						id="cr-from"
						error={form.errors.effective_from}
						optional
						>{#snippet children({ id })}<Input
								{id}
								type="datetime-local"
								bind:value={v.effective_from}
							/>{/snippet}</FormField
					>
					<FormField label={m().common.note} id="cr-note" optional
						>{#snippet children({ id })}<Input {id} bind:value={v.note} />{/snippet}</FormField
					>
				</div>
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
