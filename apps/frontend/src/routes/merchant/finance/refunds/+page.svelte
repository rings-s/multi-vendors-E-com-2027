<script lang="ts">
	import { invalidate } from '$app/navigation';
	import Undo2Icon from '@lucide/svelte/icons/undo-2';
	import { api, call } from '#lib/api/client.js';
	import type { Refund } from '#lib/api/types.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import QueryFilter from '#lib/components/app/QueryFilter.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import RefundsTable from '#lib/components/app/RefundsTable.svelte';
	import { confirm, prompt } from '#lib/confirm.svelte.js';
	import { action } from '#lib/forms.svelte.js';
	import { m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	let busy = $state<string | null>(null);
	const FILTERS = ['', 'REQUESTED', 'PROCESSING', 'SUCCEEDED', 'REJECTED', 'FAILED'];

	async function decide(r: Refund, approve: boolean) {
		let note: string | null = null;
		if (approve) {
			if (
				!(await confirm({
					title: m().merchant.approve,
					description: m().merchant.refundRequestsTitle
				}))
			)
				return;
		} else {
			note = await prompt({ title: m().merchant.decline, minLength: 3 });
			if (note == null) return;
		}
		busy = r.id;
		await action(
			() =>
				call(
					api.POST('/api/v1/merchant/refunds/{refund_id}/decision', {
						params: { path: { refund_id: r.id } },
						body: { approve, note }
					})
				),
			m().merchant.fulfillmentUpdated
		);
		busy = null;
		await invalidate('app:refunds');
	}
</script>

<svelte:head><title>{m().merchant.refunds} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.refundRequestsTitle} />
	<QueryFilter
		param="status"
		value={data.status ?? ''}
		label={m().common.filters}
		options={FILTERS.map((f) => ({ value: f, label: f ? statusLabel(f) : m().common.all }))}
	/>
	{#if data.refunds.items.length}
		<RefundsTable refunds={data.refunds.items} ondecide={decide} {busy} />
		<Paginator
			total={data.refunds.total}
			page={data.refunds.page}
			pageSize={data.refunds.page_size}
		/>
	{:else}
		<EmptyState icon={Undo2Icon} title={m().merchant.noRefunds} />
	{/if}
</div>
