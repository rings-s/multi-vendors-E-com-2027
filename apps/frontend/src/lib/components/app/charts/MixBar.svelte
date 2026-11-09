<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import { baseOptions, type ChartTheme } from '#lib/charts/chartjs.svelte.js';
	import ChartCanvas from '#lib/components/app/charts/ChartCanvas.svelte';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import { dir, fmt, locale, m } from '#lib/i18n/state.svelte.js';

	/**
	 * One whole split into at most four parts (the API folds the rest into "Other"):
	 * a single segmented bar in the validated categorical order, 2px surface gaps
	 * between segments, and a legend that always shows each part's values as text.
	 */
	interface Part {
		key: string;
		label: string;
		count: number;
		amount: number;
	}

	let { title, parts }: { title: string; parts: Part[] } = $props();

	const SLOTS = ['bg-chart-1', 'bg-chart-4', 'bg-chart-5', 'bg-chart-6'];
	const total = $derived(parts.reduce((s, p) => s + p.amount, 0));
	const share = (amount: number) => (total ? Math.round((amount / total) * 1000) / 10 : 0);

	function config(theme: ChartTheme): ChartConfiguration {
		const rtl = dir() === 'rtl';
		const base = baseOptions(theme, locale(), rtl);
		return {
			type: 'bar',
			data: {
				labels: [title],
				datasets: parts.map((p, i) => ({
					label: p.label,
					data: [p.amount],
					backgroundColor: theme.categorical[i % theme.categorical.length],
					borderColor: theme.surface,
					borderWidth: 2,
					borderRadius: 4,
					borderSkipped: false,
					barPercentage: 1,
					categoryPercentage: 1
				}))
			},
			options: {
				...base,
				indexAxis: 'y',
				interaction: { mode: 'nearest', intersect: true },
				plugins: {
					...base.plugins,
					tooltip: {
						...base.plugins?.tooltip,
						callbacks: {
							title: () => '',
							label: (item) => {
								const p = parts[item.datasetIndex];
								return p
									? `${p.label}: ${fmt.percent(share(p.amount))} · ${fmt.money(p.amount)}`
									: '';
							}
						}
					}
				},
				scales: {
					x: { display: false, stacked: true, reverse: rtl, max: total },
					y: { display: false, stacked: true }
				}
			}
		} as ChartConfiguration;
	}
</script>

<figure class="flex flex-col gap-4">
	<figcaption class="flex flex-wrap items-baseline justify-between gap-2">
		<span class="text-sm font-medium text-ink">{title}</span>
		{#if total > 0}<span class="text-sm text-ink-3 tabular">{fmt.money(total)}</span>{/if}
	</figcaption>
	{#if total === 0}
		<Empty.Root class="h-24 bg-surface-2">
			<Empty.Description>{m().analytics.noData}</Empty.Description>
		</Empty.Root>
	{:else}
		<ChartCanvas {config} class="h-9" />
		<!-- The legend doubles as the table view: every value is visible as text. -->
		<ul class="flex flex-col gap-2">
			{#each parts as p, i (p.key)}
				<li class="flex items-center gap-2 text-sm">
					<span class="size-2.5 shrink-0 rounded-xs {SLOTS[i % SLOTS.length]}" aria-hidden="true"
					></span>
					<span class="min-w-0 truncate text-ink"><bdi>{p.label}</bdi></span>
					<span class="ms-auto shrink-0 ps-2 text-ink-3 tabular">
						{fmt.percent(share(p.amount))} · {m().stores.orders({ n: p.count })}
					</span>
				</li>
			{/each}
		</ul>
	{/if}
</figure>
