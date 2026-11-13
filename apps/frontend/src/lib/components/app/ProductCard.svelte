<script lang="ts">
	import type { Product } from '#lib/api/types.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import Picture from './Picture.svelte';
	import PriceTag from './PriceTag.svelte';

	let { product, showStore = true }: { product: Product; showStore?: boolean } = $props();
	const image = $derived(product.images[0]);
	const onSale = $derived(
		product.discounted_price != null && product.discounted_price < product.price
	);
	const pct = $derived(
		onSale
			? Math.round(((product.price - (product.discounted_price ?? 0)) / product.price) * 100)
			: 0
	);
	let media = $state<HTMLElement>();

	/** Hand this card's image to the page transition so it travels to the product page. */
	function carry() {
		for (const el of document.querySelectorAll<HTMLElement>('[data-product-media]')) {
			el.style.removeProperty('view-transition-name');
		}
		media?.style.setProperty('view-transition-name', 'product-media');
	}
</script>

<!-- The image is the card: no frame around it, details set directly beneath. -->
<a
	href="/products/{product.id}"
	class="group flex h-full flex-col gap-3 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-4 focus-visible:ring-offset-background"
	data-testid="product-card"
	onclick={carry}
>
	<div
		bind:this={media}
		data-product-media
		class="relative aspect-square overflow-hidden rounded-xl bg-surface-2 ring-1 ring-edge"
	>
		<Picture
			src={image?.url}
			alt={image?.alt || product.title}
			fallback={product.title}
			class="transition-transform duration-500 ease-(--ease-out) group-hover:scale-[1.04]"
		/>
		{#if !product.in_stock}
			<span
				class="absolute start-2 top-2 rounded-md bg-card/95 px-2 py-1 text-xs font-medium text-ink shadow-pill"
			>
				{m().catalog.outOfStock}
			</span>
		{:else if onSale}
			<span
				class="absolute start-2 top-2 rounded-md bg-sale px-2 py-1 text-xs font-semibold text-white dark:text-background"
			>
				{m().catalog.save({ pct })}
			</span>
		{/if}
	</div>
	<div class="flex flex-1 flex-col gap-1">
		{#if showStore}
			<p class="truncate text-[0.8125rem] text-ink-3"><bdi>{product.store.name}</bdi></p>
		{/if}
		<h3
			class="line-clamp-2 text-[0.9375rem] leading-snug font-medium text-ink decoration-ink/30 underline-offset-4 group-hover:underline"
		>
			<bdi>{product.title}</bdi>
		</h3>
		<PriceTag
			price={product.price}
			discounted={product.discounted_price}
			size="sm"
			saving={false}
			class="mt-auto pt-1"
		/>
	</div>
</a>
