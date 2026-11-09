<script lang="ts">
	import DashboardAnalytics from '#lib/components/app/DashboardAnalytics.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatCard from '#lib/components/app/StatCard.svelte';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const o = $derived(data.overview);
	const t = $derived(m().admin);
</script>

<svelte:head><title>{t.overview} · {t.title}</title></svelte:head>

{#snippet linkCard(href: string, label: string, value: string, attention: boolean)}
	<a
		{href}
		class="rounded-2xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
	>
		<StatCard
			{label}
			{value}
			tone={attention ? 'danger' : 'default'}
			class="h-full transition-shadow hover:shadow-soft"
		/>
	</a>
{/snippet}

<div class="flex flex-col gap-8" data-testid="admin-overview">
	<PageHeader title={t.overview} />
	<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
		<StatCard label={t.grossSales} value={fmt.money(o.gross_marketplace_sales)} tone="brand" />
		<StatCard label={t.platformRevenue} value={fmt.money(o.platform_revenue)} />
		<StatCard
			label={t.paymentSuccessRate}
			value={o.payment_success_rate == null ? '—' : fmt.percent(o.payment_success_rate * 100)}
		/>
		<StatCard label={t.totalOrders} value={fmt.number(o.total_orders)} />
		<StatCard label={t.refundVolume} value={fmt.money(o.refund_volume)} />
		<StatCard label={t.settlementVolume} value={fmt.money(o.settlement_volume)} />
		<StatCard label={t.totalCustomers} value={fmt.number(o.total_customers)} />
		<StatCard
			label={t.activeMerchants}
			value="{fmt.number(o.active_merchants)} / {fmt.number(o.total_merchants)}"
		/>
	</div>
	<div class="grid gap-4 sm:grid-cols-3">
		{@render linkCard(
			'/admin/merchants?status=SUBMITTED',
			t.pendingApplications,
			fmt.number(o.pending_merchant_applications),
			o.pending_merchant_applications > 0
		)}
		{@render linkCard(
			'/admin/orders?cancellation_requested=true',
			t.pendingCancellations,
			fmt.number(o.pending_cancellations),
			o.pending_cancellations > 0
		)}
		{@render linkCard(
			'/admin/webhooks?status=FAILED',
			t.failedWebhooks,
			fmt.number(o.failed_webhooks),
			o.failed_webhooks > 0
		)}
	</div>
	<DashboardAnalytics analytics={data.analytics} periods={data.periods} scope="marketplace" />
</div>
