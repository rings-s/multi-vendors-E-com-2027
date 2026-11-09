<script lang="ts">
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import ProductForm from '#lib/components/app/ProductForm.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().merchant.editProduct} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.editProduct} description={data.product.title}>
		{#snippet meta()}<StatusBadge status={data.product.status} />{/snippet}
		{#snippet actions()}
			{#if data.product.status === 'ACTIVE'}<Button
					href="/products/{data.product.id}"
					variant="outline"
					target="_blank">{m().common.view}</Button
				>{/if}
		{/snippet}
	</PageHeader>
	{#key data.product.id}
		<ProductForm product={data.product} categories={data.categories} />
	{/key}
</div>
