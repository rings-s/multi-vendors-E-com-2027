<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import type { WeekdayPoint } from '#lib/api/types.js';
	import { axis, baseOptions, type ChartTheme } from '#lib/charts/chartjs.svelte.js';
	import ChartCanvas from '#lib/components/app/charts/ChartCanvas.svelte';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { intlTag } from '#lib/i18n/index.js';
	import { dir, fmt, locale, m } from '#lib/i18n/state.svelte.js';

	/** Average orders per weekday over the period (Sunday first, the Saudi work week). */
	let { points, title }: { points: WeekdayPoint[]; title: string } = $props();

	// 2023-01-01 was a Sunday: weekday `w` is 2023-01-0{1 + w}.
	const names = $derived.by(() => {
		const long = new Intl.DateTimeFormat(intlTag(locale()), { weekday: 'long', timeZone: 'UTC' });
		const short = new Intl.DateTimeFormat(intlTag(locale()), { weekday: 'short', timeZone: 'UTC' });
		const day = (w: number) => new Date(Date.UTC(2023, 0, 1 + w));
		return points.map((p) => ({
			long: long.format(day(p.weekday)),
			short: short.format(day(p.weekday))
		}));
	});
	const empty = $derived(points.every((p) => p.average_orders === 0));

	function avg(n: number): string {
		return new Intl.NumberFormat(intlTag(locale()), { maximumFractionDigits: 1 }).format(n);
	}

	function config(theme: ChartTheme): ChartConfiguration {
		const rtl = dir() === 'rtl';
		const base = baseOptions(theme, locale(), rtl);
		return {
			type: 'bar',
			data: {
				labels: names.map((n) => n.short),
				datasets: [
					{
						label: m().analytics.averageOrders,
						data: points.map((p) => p.average_orders),
						backgroundColor: theme.brand,
						borderRadius: 4,
						borderSkipped: 'start',
						categoryPercentage: 0.8,
						barPercentage: 0.8
					}
				]
			},
			options: {
				...base,
				interaction: { mode: 'index', intersect: false },
				plugins: {
					...base.plugins,
					tooltip: {
						...base.plugins?.tooltip,
						callbacks: {
							title: (items) => names[items[0]?.dataIndex ?? 0]?.long ?? '',
							label: (item) => {
								const p = points[item.dataIndex];
								return [
									`${m().analytics.averageOrders}: ${avg(Number(item.raw))}`,
									`${m().analytics.averageSales}: ${fmt.money(p?.average_gross_sales)}`
								];
							}
						}
					}
				},
				scales: {
					x: {
						...axis(theme, false),
						reverse: rtl,
						ticks: { ...axis(theme, false).ticks, maxRotation: 0, autoSkip: true }
					},
					y: {
						...axis(theme, true),
						position: rtl ? 'right' : 'left',
						beginAtZero: true,
						ticks: {
							...axis(theme, true).ticks,
							maxTicksLimit: 4,
							callback: (v) => avg(Number(v))
						}
					}
				}
			}
		} as ChartConfiguration;
	}
</script>

<figure class="flex flex-col gap-4">
	<figcaption class="flex flex-col gap-0.5">
		<span class="text-sm font-medium text-ink">{title}</span>
		<span class="text-xs text-ink-3">{m().analytics.weekdaysHint}</span>
	</figcaption>
	{#if empty}
		<Empty.Root class="h-52 bg-surface-2">
			<Empty.Description>{m().analytics.noData}</Empty.Description>
		</Empty.Root>
	{:else}
		<ChartCanvas {config} class="h-52" />
		<div class="sr-only">
			<Table.Root>
				<Table.Caption>{title}</Table.Caption>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().analytics.weekday}</Table.Head>
						<Table.Head>{m().analytics.averageOrders}</Table.Head>
						<Table.Head>{m().analytics.averageSales}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each points as p, i (p.weekday)}
						<Table.Row>
							<Table.Cell>{names[i]?.long}</Table.Cell>
							<Table.Cell>{avg(p.average_orders)}</Table.Cell>
							<Table.Cell>{fmt.money(p.average_gross_sales)}</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</figure>
