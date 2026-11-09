<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import type { Snippet } from 'svelte';
	import { axis, baseOptions, compact, type ChartTheme } from '#lib/charts/chartjs.svelte.js';
	import ChartCanvas from '#lib/components/app/charts/ChartCanvas.svelte';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { dir, fmt, locale, m } from '#lib/i18n/state.svelte.js';

	/**
	 * Daily gross sales, straight from the API (never fabricated or interpolated).
	 * With `moving_average` on the points, the daily bars recede and the trailing
	 * average is drawn on the same (single) axis as the emphasized line.
	 */
	interface Point {
		date: string;
		orders: number;
		gross_sales: number;
		moving_average?: number;
	}

	interface Props {
		points: Point[];
		title: string;
		movingAverageDays?: number;
		/** Extra line under the title (e.g. the trend). */
		caption?: Snippet;
	}

	let { points, title, movingAverageDays, caption }: Props = $props();

	const total = $derived(points.reduce((s, p) => s + p.gross_sales, 0));
	const orders = $derived(points.reduce((s, p) => s + p.orders, 0));
	const withAverage = $derived(
		movingAverageDays != null && points.some((p) => p.moving_average != null)
	);
	const averageLabel = $derived(m().analytics.movingAverage({ n: movingAverageDays ?? 7 }));

	function config(theme: ChartTheme): ChartConfiguration {
		const rtl = dir() === 'rtl';
		const base = baseOptions(theme, locale(), rtl);
		const labels = points.map((p) => p.date);
		const datasets: ChartConfiguration<'bar' | 'line'>['data']['datasets'] = [
			{
				type: 'bar',
				label: m().analytics.dailySales,
				data: points.map((p) => p.gross_sales),
				backgroundColor: withAverage ? theme.recessive : theme.brand,
				hoverBackgroundColor: withAverage ? theme.ink3 : theme.brand,
				borderRadius: 4,
				borderSkipped: 'start',
				categoryPercentage: 0.84,
				barPercentage: 0.92,
				order: 2
			}
		];
		if (withAverage) {
			datasets.push({
				type: 'line',
				label: averageLabel,
				data: points.map((p) => p.moving_average ?? 0),
				borderColor: theme.brand,
				backgroundColor: theme.brand,
				borderWidth: 2,
				pointRadius: 0,
				pointHitRadius: 12,
				pointHoverRadius: 5,
				pointHoverBorderWidth: 2,
				pointHoverBorderColor: theme.surface,
				tension: 0.3,
				order: 1
			});
		}
		return {
			type: 'bar',
			data: { labels, datasets },
			options: {
				...base,
				interaction: { mode: 'index', intersect: false },
				plugins: {
					...base.plugins,
					tooltip: {
						...base.plugins?.tooltip,
						callbacks: {
							title: (items) => {
								const p = points[items[0]?.dataIndex ?? 0];
								return p ? `${fmt.date(p.date)} · ${m().stores.orders({ n: p.orders })}` : '';
							},
							label: (item) => `${item.dataset.label}: ${fmt.money(Number(item.raw))}`
						}
					}
				},
				scales: {
					x: {
						...axis(theme, false),
						reverse: rtl,
						ticks: {
							...axis(theme, false).ticks,
							autoSkip: true,
							maxTicksLimit: 6,
							maxRotation: 0,
							callback: (_v, i) => fmt.shortDate(labels[i])
						}
					},
					y: {
						...axis(theme, true),
						position: rtl ? 'right' : 'left',
						beginAtZero: true,
						ticks: {
							...axis(theme, true).ticks,
							maxTicksLimit: 5,
							callback: (v) => compact(Number(v) / 100, locale())
						}
					}
				}
			}
		} as ChartConfiguration;
	}
</script>

<figure class="flex flex-col gap-4">
	<figcaption class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
		<span class="flex flex-col gap-0.5">
			<span class="text-sm font-medium text-ink">{title}</span>
			{#if caption}<span class="text-xs text-ink-3">{@render caption()}</span>{/if}
		</span>
		<span class="text-sm text-ink-3 tabular">
			{fmt.money(total)} · {m().stores.orders({ n: orders })}
		</span>
	</figcaption>
	{#if total === 0}
		<Empty.Root class="h-52 bg-surface-2">
			<Empty.Description>{m().merchant.noSales}</Empty.Description>
		</Empty.Root>
	{:else}
		{#if withAverage}
			<ul class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-3" aria-hidden="true">
				<li class="flex items-center gap-1.5">
					<span class="size-2.5 rounded-xs bg-chart-3"></span>{m().analytics.dailySales}
				</li>
				<li class="flex items-center gap-1.5">
					<span class="h-0.5 w-3 rounded-full bg-chart-1"></span>{averageLabel}
				</li>
			</ul>
		{/if}
		<ChartCanvas {config} class="h-52" />
		<div class="sr-only">
			<Table.Root>
				<Table.Caption>{title}</Table.Caption>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().common.date}</Table.Head>
						<Table.Head>{m().common.amount}</Table.Head>
						{#if withAverage}<Table.Head>{averageLabel}</Table.Head>{/if}
						<Table.Head>{m().nav.orders}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each points as p (p.date)}
						<Table.Row>
							<Table.Cell>{fmt.date(p.date)}</Table.Cell>
							<Table.Cell>{fmt.money(p.gross_sales)}</Table.Cell>
							{#if withAverage}<Table.Cell>{fmt.money(p.moving_average)}</Table.Cell>{/if}
							<Table.Cell>{p.orders}</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</figure>
