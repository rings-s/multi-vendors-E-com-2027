<script lang="ts">
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import CatalogFilters from '#lib/components/app/CatalogFilters.svelte';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import ServiceCard from '#lib/components/app/ServiceCard.svelte';
	import { m, pick } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const category = $derived(data.categories.find((c) => c.slug === data.filters.category));
	const title = $derived(category ? pick(category, 'name') : m().catalog.servicesTitle);
</script>

<svelte:head><title>{title} · {m().brand.name}</title></svelte:head>

<div class="container-page flex flex-col gap-8 py-12">
	<PageHeader {title} description={m().catalog.servicesSubtitle} size="lg" />
	<CatalogFilters filters={data.filters} categories={data.categories} kind="SERVICE" />
	{#if data.services.items.length}
		<div class="grid gap-4 md:grid-cols-2">
			{#each data.services.items as service (service.id)}
				<ServiceCard {service} />
			{/each}
		</div>
		<Paginator
			total={data.services.total}
			page={data.services.page}
			pageSize={data.services.page_size}
		/>
	{:else}
		<EmptyState
			icon={SparklesIcon}
			title={m().catalog.emptyTitle}
			description={m().catalog.emptyBody}
		/>
	{/if}
</div>
