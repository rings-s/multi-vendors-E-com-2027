<script lang="ts">
	import type { Analytics, Delta, RateDelta } from '#lib/api/types.js';
	import { compact } from '#lib/charts/chartjs.svelte.js';
	import MixBar from '#lib/components/app/charts/MixBar.svelte';
	import RankedBarChart from '#lib/components/app/charts/RankedBarChart.svelte';
	import WeekdayChart from '#lib/components/app/charts/WeekdayChart.svelte';
	import QueryFilter from '#lib/components/app/QueryFilter.svelte';
	import SalesChart from '#lib/components/app/SalesChart.svelte';
	import StatCard from '#lib/components/app/StatCard.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import { fmt, locale, m, statusLabel } from '#lib/i18n/state.svelte.js';

	/**
	 * The period-scoped part of a dashboard: one period filter above everything it
	 * scopes, KPI tiles against the previous period, then the charts.
	 */
	interface Props {
		analytics: Analytics;
		periods: number[];
		/** The marketplace view adds the top-merchants ranking. */
		scope: 'marketplace' | 'merchant';
	}

	let { analytics: a, periods, scope }: Props = $props();
	const t = $derived(m().analytics);

	function signed(n: number, format: (abs: number) => string): string {
		return `${n > 0 ? '+' : n < 0 ? '−' : ''}${format(Math.abs(n))}`;
	}

	function direction(n: number | null | undefined): 'up' | 'down' | 'flat' {
		return !n ? 'flat' : n > 0 ? 'up' : 'down';
	}

	/** Relative change; more is good news for sales, orders and order value. */
	function change(d: Delta) {
		if (d.change_pct == null) {
			return { text: t.noPrevious, direction: 'flat', sentiment: 'neutral' } as const;
		}
		const dir = direction(d.change_pct);
		return {
			text: t.vsPrevious({ change: signed(d.change_pct, fmt.percent) }),
			direction: dir,
			sentiment: dir === 'up' ? 'good' : dir === 'down' ? 'bad' : 'neutral'
		} as const;
	}

	/** Change in points; a rising refund rate is bad news. */
	function rateChange(d: RateDelta) {
		if (d.change_points == null) {
			return { text: t.noPrevious, direction: 'flat', sentiment: 'neutral' } as const;
		}
		const dir = direction(d.change_points);
		return {
			text: t.pointsVsPrevious({
				change: signed(d.change_points, (n) => fmt.number(Math.round(n * 100) / 100))
			}),
			direction: dir,
			sentiment: dir === 'up' ? 'bad' : dir === 'down' ? 'good' : 'neutral'
		} as const;
	}

	const moneyTick = (halalas: number) => compact(halalas / 100, locale());
	const methodLabel = (key: string) => (t.methods as Record<string, string>)[key] ?? key;
</script>

<section class="flex flex-col gap-4" aria-labelledby="analytics-title" data-testid="analytics">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div class="flex flex-col gap-1">
			<h2 id="analytics-title" class="type-title">{t.title}</h2>
			<p class="text-sm text-ink-3">{t.description({ n: a.days })}</p>
		</div>
		<QueryFilter
			param="days"
			value={String(a.days)}
			label={t.period}
			options={periods.map((d) => ({ value: String(d), label: m().merchant.days({ n: d }) }))}
		/>
	</div>

	<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
		<StatCard
			label={t.grossSales}
			value={fmt.money(a.kpis.gross_sales.current)}
			delta={change(a.kpis.gross_sales)}
		/>
		<StatCard
			label={t.orders}
			value={fmt.number(a.kpis.orders.current)}
			delta={change(a.kpis.orders)}
		/>
		<StatCard
			label={t.averageOrder}
			value={fmt.money(a.kpis.average_order_value.current)}
			delta={change(a.kpis.average_order_value)}
			hint={t.medianOrder({ value: fmt.money(a.kpis.median_order_value.current) })}
		/>
		<StatCard
			label={t.refundRate}
			value={a.kpis.refund_rate.current == null ? '—' : fmt.percent(a.kpis.refund_rate.current)}
			delta={rateChange(a.kpis.refund_rate)}
		/>
	</div>

	<div class="grid gap-4 lg:grid-cols-3">
		<Card.Root class="lg:col-span-2">
			<Card.Content>
				<SalesChart
					points={a.trend.points}
					movingAverageDays={a.trend.moving_average_days}
					title={t.dailySales}
				>
					{#snippet caption()}
						{#if a.trend.slope_per_day != null}
							{t.trendPerDay({ value: signed(a.trend.slope_per_day, fmt.money) })}
						{/if}
					{/snippet}
				</SalesChart>
			</Card.Content>
		</Card.Root>
		<Card.Root>
			<Card.Content>
				<WeekdayChart points={a.weekdays} title={t.weekdays} />
			</Card.Content>
		</Card.Root>
	</div>

	<div class="grid gap-4 lg:grid-cols-2">
		{#if scope === 'marketplace'}
			<Card.Root>
				<Card.Content>
					<RankedBarChart
						title={t.topMerchants}
						labelHeading={t.merchant}
						valueHeading={t.grossSales}
						format={fmt.money}
						tick={moneyTick}
						rows={a.top_merchants.map((r) => ({
							key: r.id,
							label: r.label,
							value: r.amount,
							detail: m().stores.orders({ n: r.count })
						}))}
					/>
				</Card.Content>
			</Card.Root>
		{/if}
		<Card.Root>
			<Card.Content>
				<RankedBarChart
					title={t.topItems}
					labelHeading={t.item}
					valueHeading={t.grossSales}
					format={fmt.money}
					tick={moneyTick}
					rows={a.top_items.map((r) => ({
						key: r.id,
						label: r.label,
						value: r.amount,
						detail: t.unitsSold({ n: r.count })
					}))}
				/>
			</Card.Content>
		</Card.Root>
		<Card.Root>
			<Card.Content>
				<RankedBarChart
					title={t.orderStatuses}
					labelHeading={m().common.status}
					valueHeading={t.orders}
					format={fmt.number}
					rows={a.order_statuses.map((s) => ({
						key: s.key,
						label: statusLabel(s.key),
						value: s.count,
						detail: fmt.money(s.amount)
					}))}
				/>
			</Card.Content>
		</Card.Root>
		<Card.Root class={scope === 'marketplace' ? '' : 'lg:col-span-2'}>
			<Card.Content>
				<MixBar
					title={t.paymentMethods}
					parts={a.payment_methods.map((p) => ({ ...p, label: methodLabel(p.key) }))}
				/>
			</Card.Content>
		</Card.Root>
	</div>
</section>
