<script lang="ts">
	import { Chart, type ChartConfiguration } from 'chart.js';
	import { untrack } from 'svelte';
	import { readTheme, themeVersion, type ChartTheme } from '#lib/charts/chartjs.svelte.js';
	import { cn } from '#lib/utils.js';

	/**
	 * A Chart.js canvas. `config` is called with the resolved theme tokens and re-run
	 * whenever the data it reads or the theme changes; the existing chart is updated in
	 * place (no flash, animated), and destroyed with the component.
	 *
	 * The canvas is decorative for assistive tech (`aria-hidden`): every chart renders a
	 * table with the same values next to it.
	 */
	interface Props {
		config: (theme: ChartTheme) => ChartConfiguration;
		/** Pixel height when it depends on the data (e.g. one row per bar); otherwise use `class`. */
		height?: number;
		class?: string;
	}

	let { config, height, class: className }: Props = $props();

	let canvas: HTMLCanvasElement | undefined = $state();
	let chart: Chart | undefined;
	let type: string | undefined;
	// Always created with its own array, so later updates can swap the inline plugins.
	let plugins: NonNullable<ChartConfiguration['plugins']> = [];

	function create(target: HTMLCanvasElement, next: ChartConfiguration) {
		plugins = [...(next.plugins ?? [])];
		type = next.type;
		chart = new Chart(target, { ...next, plugins });
	}

	$effect(() => {
		if (!canvas) return;
		const target = canvas;
		themeVersion();
		const next = config(readTheme(target));
		untrack(() => {
			if (!chart || type !== next.type) {
				chart?.destroy();
				create(target, next);
				return;
			}
			chart.data = next.data;
			chart.options = next.options ?? {};
			// `config.plugins` has no setter; Chart.js re-resolves this array on update().
			plugins.splice(0, plugins.length, ...(next.plugins ?? []));
			chart.update();
		});
	});

	$effect(() => () => {
		chart?.destroy();
		chart = undefined;
	});
</script>

<div class={cn('relative w-full', className)} style:height={height ? `${height}px` : undefined}>
	<canvas bind:this={canvas} aria-hidden="true"></canvas>
</div>
