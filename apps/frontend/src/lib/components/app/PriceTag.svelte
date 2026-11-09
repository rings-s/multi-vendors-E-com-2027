<script lang="ts">
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		price: number;
		discounted?: number | null;
		size?: 'sm' | 'md' | 'lg';
		class?: string;
	}

	let { price, discounted, size = 'md', class: className }: Props = $props();
	const onSale = $derived(discounted != null && discounted < price);
	const pct = $derived(onSale ? Math.round(((price - (discounted ?? price)) / price) * 100) : 0);
</script>

<div class={cn('flex flex-wrap items-baseline gap-x-2 gap-y-1 tabular', className)}>
	<span
		class={cn(
			'font-semibold tracking-[-0.025em] text-ink',
			size === 'lg'
				? 'text-[1.75rem] tracking-[-0.04em]'
				: size === 'sm'
					? 'text-[0.9375rem]'
					: 'text-base'
		)}
	>
		{fmt.money(onSale ? discounted : price)}
	</span>
	{#if onSale}
		<s class="text-sm text-ink-3">{fmt.money(price)}</s>
		<Badge variant="sale">{m().catalog.save({ pct })}</Badge>
	{/if}
</div>
