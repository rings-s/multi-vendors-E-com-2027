<script lang="ts">
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		price: number;
		discounted?: number | null;
		size?: 'sm' | 'md' | 'lg';
		/** Show the saving next to the price (off when a badge already says it). */
		saving?: boolean;
		class?: string;
	}

	let { price, discounted, size = 'md', saving = true, class: className }: Props = $props();
	const onSale = $derived(discounted != null && discounted < price);
	const pct = $derived(onSale ? Math.round(((price - (discounted ?? price)) / price) * 100) : 0);
</script>

<!-- Current price leads; a discount shows the old price struck through and the saving in red. -->
<div class={cn('flex flex-wrap items-baseline gap-x-2 gap-y-0.5 tabular', className)}>
	<span
		class={cn(
			'font-semibold text-ink',
			size === 'lg'
				? 'text-[1.75rem] leading-tight tracking-[-0.025em]'
				: size === 'sm'
					? 'text-[0.9375rem]'
					: 'text-base'
		)}
	>
		{fmt.money(onSale ? discounted : price)}
	</span>
	{#if onSale}
		<s class={cn('text-ink-3', size === 'lg' ? 'text-base' : 'text-[0.8125rem]')}
			>{fmt.money(price)}</s
		>
		{#if saving}
			<span class={cn('font-semibold text-sale', size === 'lg' ? 'text-sm' : 'text-xs')}
				>{m().catalog.save({ pct })}</span
			>
		{/if}
	{/if}
</div>
