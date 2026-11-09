<script lang="ts">
	import { invalidate } from '$app/navigation';
	import WebhookIcon from '@lucide/svelte/icons/webhook';
	import { api, call } from '#lib/api/client.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import QueryFilter from '#lib/components/app/QueryFilter.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	let busy = $state<string | null>(null);

	async function reprocess(id: string) {
		busy = id;
		await action(
			() =>
				call(
					api.POST('/api/v1/admin/webhook-events/{event_id}/reprocess', {
						params: { path: { event_id: id } }
					})
				),
			m().common.saved
		);
		busy = null;
		await invalidate('app:webhooks');
	}
</script>

<svelte:head><title>{t.webhooks} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.webhooks} />
	<QueryFilter
		param="status"
		value={data.status ?? ''}
		label={m().common.filters}
		options={['', 'RECEIVED', 'PROCESSED', 'FAILED', 'IGNORED'].map((s) => ({
			value: s,
			label: s ? statusLabel(s) : m().common.all
		}))}
	/>
	{#if data.events.items.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{t.event}</Table.Head>
						<Table.Head>{m().merchant.provider}</Table.Head>
						<Table.Head>{m().common.date}</Table.Head>
						<Table.Head class="text-end">{t.attempts}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
						<Table.Head><span class="sr-only">{m().common.actions}</span></Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.events.items as e (e.id)}
						<Table.Row>
							<Table.Cell
								><p class="font-medium" dir="ltr">{e.event_type}</p>
								<p class="text-xs text-ink-3 tabular" dir="ltr">{e.event_id}</p>
								{#if e.last_error}<p class="text-xs text-danger">{e.last_error}</p>{/if}</Table.Cell
							>
							<Table.Cell class="capitalize"
								>{e.provider}{#if !e.is_live}
									· {m().common.testMode}{/if}</Table.Cell
							>
							<Table.Cell class="text-ink-3">{fmt.datetime(e.created_at)}</Table.Cell>
							<Table.Cell class="text-end tabular">{e.attempts}</Table.Cell>
							<Table.Cell><StatusBadge status={e.status} /></Table.Cell>
							<Table.Cell class="text-end"
								>{#if e.status === 'FAILED' || e.status === 'RECEIVED'}<Button
										size="sm"
										variant="outline"
										disabled={busy === e.id}
										onclick={() => reprocess(e.id)}>{t.reprocess}</Button
									>{/if}</Table.Cell
							>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator total={data.events.total} page={data.events.page} pageSize={data.events.page_size} />
	{:else}
		<EmptyState icon={WebhookIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>
