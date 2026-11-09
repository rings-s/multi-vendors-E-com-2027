<script lang="ts">
	import PackageSearchIcon from '@lucide/svelte/icons/package-search';
	import CatalogFilters from '#lib/components/app/CatalogFilters.svelte';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import ProductCard from '#lib/components/app/ProductCard.svelte';
	import { m, pick } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const category = $derived(data.categories.find((c) => c.slug === data.filters.category));
	const title = $derived(category ? pick(category, 'name') : m().catalog.productsTitle);
</script>

<svelte:head><title>{title} · {m().brand.name}</title></svelte:head>

<div class="container-page flex flex-col gap-8 py-12">
	<PageHeader
		{title}
		description={m().catalog.productsSubtitle}
		size="lg"
		eyebrow={category ? m().nav.products : undefined}
	/>
	<CatalogFilters filters={data.filters} categories={data.categories} kind="PRODUCT" />
	{#if data.products.items.length}
		<p class="text-sm text-ink-3">{m().common.results({ count: data.products.total })}</p>
		<div class="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-3 lg:grid-cols-4">
			{#each data.products.items as product (product.id)}
				<ProductCard {product} />
			{/each}
		</div>
		<Paginator
			total={data.products.total}
			page={data.products.page}
			pageSize={data.products.page_size}
		/>
	{:else}
		<EmptyState
			icon={PackageSearchIcon}
			title={m().catalog.emptyTitle}
			description={m().catalog.emptyBody}
		/>
	{/if}
</div>
