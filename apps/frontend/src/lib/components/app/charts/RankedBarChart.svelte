<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import {
		axis,
		barEndLabelRoom,
		barEndLabels,
		baseOptions,
		compact,
		type ChartTheme
	} from '#lib/charts/chartjs.svelte.js';
	import ChartCanvas from '#lib/components/app/charts/ChartCanvas.svelte';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { dir, locale, m } from '#lib/i18n/state.svelte.js';

	/**
	 * Ranked horizontal bars for one measure over nominal categories: one series, one
	 * color (no value ramp), value written at each bar's end in muted ink.
	 */
	interface Row {
		key: string;
		label: string;
		value: number;
		/** Secondary figure for the tooltip and table (e.g. "3 orders"). */
		detail?: string;
	}

	interface Props {
		title: string;
		rows: Row[];
		/** Header of the label column in the table view. */
		labelHeading: string;
		valueHeading: string;
		format: (value: number) => string;
		/** Axis ticks for large values (money in halalas). Defaults to compact numbers. */
		tick?: (value: number) => string;
	}

	let { title, rows, labelHeading, valueHeading, format, tick }: Props = $props();

	const ROW_HEIGHT = 36;
	const height = $derived(rows.length * ROW_HEIGHT + 32);

	function truncate(text: string, max = 22): string {
		return text.length > max ? `${text.slice(0, max - 1)}…` : text;
	}

	function config(theme: ChartTheme): ChartConfiguration {
		const rtl = dir() === 'rtl';
		const base = baseOptions(theme, locale(), rtl);
		const room = barEndLabelRoom(
			rows.map((r) => format(r.value)),
			theme.font
		);
		return {
			type: 'bar',
			data: {
				labels: rows.map((r) => r.label),
				datasets: [
					{
						label: valueHeading,
						data: rows.map((r) => r.value),
						backgroundColor: theme.brand,
						borderRadius: 4,
						borderSkipped: 'start',
						barPercentage: 0.72,
						categoryPercentage: 1
					}
				]
			},
			options: {
				...base,
				indexAxis: 'y',
				// Room past the longest bar for its value label.
				layout: { padding: rtl ? { left: room } : { right: room } },
				interaction: { mode: 'nearest', axis: 'y', intersect: false },
				plugins: {
					...base.plugins,
					tooltip: {
						...base.plugins?.tooltip,
						callbacks: {
							title: (items) => rows[items[0]?.dataIndex ?? 0]?.label ?? '',
							label: (item) => {
								const row = rows[item.dataIndex];
								return row?.detail
									? `${format(Number(item.raw))} · ${row.detail}`
									: format(Number(item.raw));
							}
						}
					}
				},
				scales: {
					x: {
						...axis(theme, true),
						reverse: rtl,
						beginAtZero: true,
						ticks: {
							...axis(theme, true).ticks,
							maxTicksLimit: 4,
							callback: (v) => (tick ? tick(Number(v)) : compact(Number(v), locale()))
						}
					},
					y: {
						...axis(theme, false),
						position: rtl ? 'right' : 'left',
						ticks: {
							...axis(theme, false).ticks,
							color: theme.ink,
							font: { family: theme.font, size: 12 },
							// Chart.js caps the label column, so shorten labels on narrow charts.
							callback(_v, i) {
								return truncate(rows[i]?.label ?? '', this.chart.width < 420 ? 14 : 22);
							}
						}
					}
				}
			},
			plugins: [barEndLabels(format, theme.ink3, rtl)]
		} as ChartConfiguration;
	}
</script>

<figure class="flex flex-col gap-3">
	<figcaption class="text-sm font-medium text-ink">{title}</figcaption>
	{#if rows.length === 0}
		<Empty.Root class="h-40 bg-surface-2">
			<Empty.Description>{m().analytics.noData}</Empty.Description>
		</Empty.Root>
	{:else}
		<ChartCanvas {config} {height} />
		<div class="sr-only">
			<Table.Root>
				<Table.Caption>{title}</Table.Caption>
				<Table.Header>
					<Table.Row>
						<Table.Head>{labelHeading}</Table.Head>
						<Table.Head>{valueHeading}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each rows as r (r.key)}
						<Table.Row>
							<Table.Cell><bdi>{r.label}</bdi></Table.Cell>
							<Table.Cell>{format(r.value)}{r.detail ? ` · ${r.detail}` : ''}</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</figure>
