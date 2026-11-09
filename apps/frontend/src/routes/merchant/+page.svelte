<script lang="ts">
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import InboxIcon from '@lucide/svelte/icons/inbox';
	import ReceiptIcon from '@lucide/svelte/icons/receipt';
	import DashboardAnalytics from '#lib/components/app/DashboardAnalytics.svelte';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FinanceSummary from '#lib/components/app/FinanceSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatCard from '#lib/components/app/StatCard.svelte';
	import TransactionsTable from '#lib/components/app/TransactionsTable.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const d = $derived(data.dashboard);
</script>

<svelte:head><title>{m().merchant.dashboard} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={m().merchant.dashboard} description={data.merchant.business_name}>
		{#snippet actions()}
			{#if data.merchant.store_slug}
				<Button href="/stores/{data.merchant.store_slug}" variant="outline" target="_blank"
					><ExternalLinkIcon data-icon="inline-start" />{m().merchant.viewStorefront}</Button
				>
			{/if}
		{/snippet}
	</PageHeader>

	<div class="grid gap-4 sm:grid-cols-3">
		<StatCard
			label={m().merchant.ordersToday}
			value={fmt.number(d.orders_today)}
			icon={ReceiptIcon}
		/>
		<StatCard label={m().merchant.openOrders} value={fmt.number(d.open_orders)} icon={InboxIcon} />
		<StatCard label={m().merchant.totalOrders} value={fmt.number(d.total_orders)} />
	</div>

	<FinanceSummary summary={d.summary} />

	<DashboardAnalytics analytics={data.analytics} periods={data.periods} scope="merchant" />

	<section class="flex flex-col gap-4">
		<div class="flex items-end justify-between">
			<h2 class="type-title">{m().merchant.recentTransactions}</h2>
			<Button href="/merchant/finance/transactions" variant="link" size="sm" class="px-0"
				>{m().common.viewAll}</Button
			>
		</div>
		{#if d.recent_transactions.length}
			<TransactionsTable items={d.recent_transactions} />
		{:else}
			<EmptyState title={m().merchant.noTransactions} />
		{/if}
	</section>
</div>
