<script lang="ts">
	import LandmarkIcon from '@lucide/svelte/icons/landmark';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().merchant.settlements} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.settlements} description={m().merchant.settlementExplainer} />
	{#if data.settlements.items.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().merchant.providerReference}</Table.Head>
						<Table.Head>{m().merchant.initiated}</Table.Head>
						<Table.Head>{m().merchant.completed}</Table.Head>
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
							<Table.Cell class="text-ink-3">{fmt.datetime(s.initiated_at)}</Table.Cell>
							<Table.Cell class="text-ink-3">{fmt.datetime(s.completed_at)}</Table.Cell>
							<Table.Cell
								>{s.confirmation_source ? statusLabel(s.confirmation_source) : '—'}</Table.Cell
							>
							<Table.Cell
								><StatusBadge status={s.status} />{#if s.failure_reason}<p
										class="mt-1 text-xs text-danger"
									>
										{s.failure_reason}
									</p>{/if}</Table.Cell
							>
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
		<EmptyState icon={LandmarkIcon} title={m().merchant.noSettlements} />
	{/if}
</div>
