<script lang="ts">
	import type { Product } from '#lib/api/types.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import Picture from './Picture.svelte';
	import PriceTag from './PriceTag.svelte';

	let { product, showStore = true }: { product: Product; showStore?: boolean } = $props();
	const image = $derived(product.images[0]);
</script>

<!--
	Floating product card: white surface, 28px radius, dual-layer soft shadow, no border.
	The image sits 8px inside at 20px radius, so even white-background photography keeps a frame.
-->
<a
	href="/products/{product.id}"
	class="group flex h-full flex-col rounded-2xl bg-card p-2 text-card-foreground shadow-soft ring-1 ring-edge transition-[box-shadow,translate] duration-300 ease-out hover:-translate-y-0.5 hover:shadow-lift focus-visible:ring-4 focus-visible:ring-ring/25 focus-visible:outline-none"
	data-testid="product-card"
>
	<div class="relative aspect-square overflow-hidden rounded-[20px] bg-surface-2">
		<Picture
			src={image?.url}
			alt={image?.alt || product.title}
			fallback={product.title}
			class="transition-transform duration-700 ease-out group-hover:scale-[1.04]"
		/>
		{#if !product.in_stock}
			<Badge variant="outline" class="absolute start-2.5 top-2.5 shadow-pill">
				{m().catalog.outOfStock}
			</Badge>
		{/if}
	</div>
	<div class="flex flex-1 flex-col gap-1 px-2 pt-3 pb-2">
		{#if showStore}
			<p class="truncate type-label text-ink-3"><bdi>{product.store.name}</bdi></p>
		{/if}
		<h3 class="line-clamp-2 text-sm leading-snug font-semibold tracking-[-0.02em] text-ink">
			<bdi>{product.title}</bdi>
		</h3>
		<PriceTag
			price={product.price}
			discounted={product.discounted_price}
			size="sm"
			class="mt-auto pt-1"
		/>
	</div>
</a>
