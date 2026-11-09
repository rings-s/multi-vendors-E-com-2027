<script lang="ts">
	import type { CommissionRule } from '#lib/api/types.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatCard from '#lib/components/app/StatCard.svelte';
	import * as Table from '#lib/components/ui/table/index.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const c = $derived(data.commissions);
	const rate = (r: CommissionRule) =>
		r.rate_type === 'FIXED' ? fmt.money(r.fixed_amount) : fmt.percent(r.rate);
</script>

<svelte:head><title>{m().merchant.commissions} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={m().merchant.commissions} description={m().admin.commissionNote} />
	<div class="grid gap-4 sm:grid-cols-3">
		<StatCard
			label={m().merchant.currentRule}
			value={rate(c.current_rule)}
			tone="brand"
			hint="{statusLabel(c.current_rule.scope)} · {fmt.date(c.current_rule.effective_from)}"
		/>
		{#each c.merchant_rules.filter((r) => r.id !== c.current_rule.id).slice(0, 2) as r (r.id)}
			<StatCard
				label={statusLabel(r.scope)}
				value={rate(r)}
				hint="{fmt.date(r.effective_from)} – {r.effective_to ? fmt.date(r.effective_to) : '…'}"
			/>
		{/each}
	</div>
	{#if c.transactions.items.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().common.date}</Table.Head>
						<Table.Head class="text-end">{m().merchant.gross}</Table.Head>
						<Table.Head class="text-end">{m().merchant.base}</Table.Head>
						<Table.Head class="text-end">{m().merchant.rate}</Table.Head>
						<Table.Head class="text-end">{m().merchant.commission}</Table.Head>
						<Table.Head class="text-end">{m().merchant.fee}</Table.Head>
						<Table.Head>{m().merchant.feeBearer}</Table.Head>
						<Table.Head class="text-end">{m().merchant.sellerNet}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each c.transactions.items as t (t.id)}
						<Table.Row>
							<Table.Cell class="text-ink-3">{fmt.date(t.created_at)}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(t.gross_amount)}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(t.commission_base)}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.percent(t.commission_rate)}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(t.commission_amount)}</Table.Cell>
							<Table.Cell class="text-end tabular"
								>{t.processing_fee == null ? '—' : fmt.money(t.processing_fee)}</Table.Cell
							>
							<Table.Cell>{statusLabel(t.fee_bearer)}</Table.Cell>
							<Table.Cell class="text-end font-medium tabular"
								>{fmt.money(t.seller_net_amount)}</Table.Cell
							>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={c.transactions.total}
			page={c.transactions.page}
			pageSize={c.transactions.page_size}
		/>
	{:else}
		<EmptyState title={m().merchant.noCommissions} />
	{/if}
</div>
