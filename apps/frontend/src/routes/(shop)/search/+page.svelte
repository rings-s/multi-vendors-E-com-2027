<script lang="ts">
	import { isolate } from '#lib/i18n/bidi.js';
	import { goto } from '$app/navigation';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import SearchIcon from '@lucide/svelte/icons/search';
	import SearchXIcon from '@lucide/svelte/icons/search-x';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import ProductCard from '#lib/components/app/ProductCard.svelte';
	import ServiceCard from '#lib/components/app/ServiceCard.svelte';
	import StoreCard from '#lib/components/app/StoreCard.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as InputGroup from '#lib/components/ui/input-group/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	// Follows the URL, but stays editable in the search field.
	let term = $derived(data.q);
	const r = $derived(data.results);
	const nothing = $derived(r && !r.stores.total && !r.products.total && !r.services.total);

	function submit(e: SubmitEvent) {
		e.preventDefault();
		void goto(term.trim() ? `/search?q=${encodeURIComponent(term.trim())}` : '/search');
	}
</script>

<svelte:head
	><title
		>{data.q ? m().search.resultsFor({ q: isolate(data.q) }) : m().search.title} · {m().brand
			.name}</title
	></svelte:head
>

{#snippet head(title: string, total: number, href: string)}
	<div class="mb-5 flex items-end justify-between">
		<h2 class="type-title">
			{title} <span class="text-base text-ink-3 tabular">{fmt.number(total)}</span>
		</h2>
		{#if total > 0}
			<Button {href} variant="link" size="sm" class="px-0"
				>{m().common.viewAll}<ArrowRightIcon
					class="rtl-flip"
					data-icon="inline-end"
					aria-hidden="true"
				/></Button
			>
		{/if}
	</div>
{/snippet}

<div class="container-page flex flex-col gap-12 py-12">
	<div class="mx-auto flex max-w-2xl flex-col gap-5 text-center">
		<h1 class="font-display text-4xl text-ink">
			{data.q ? m().search.resultsFor({ q: isolate(data.q) }) : m().search.prompt}
		</h1>
		<form role="search" onsubmit={submit} class="flex gap-2">
			<InputGroup.Root class="bg-surface">
				<InputGroup.Addon><SearchIcon /></InputGroup.Addon>
				<InputGroup.Input
					type="search"
					bind:value={term}
					placeholder={m().common.searchPlaceholder}
					aria-label={m().common.search}
				/>
			</InputGroup.Root>
			<Button type="submit" size="lg">{m().common.search}</Button>
		</form>
	</div>

	{#if nothing}
		<EmptyState
			icon={SearchXIcon}
			title={m().search.nothing({ q: isolate(data.q) })}
			description={m().catalog.emptyBody}
		/>
	{:else if r}
		{#if r.stores.total}
			<section>
				{@render head(
					m().search.storesSection,
					r.stores.total,
					`/stores?q=${encodeURIComponent(data.q)}`
				)}
				<div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
					{#each r.stores.items as store (store.id)}<StoreCard {store} />{/each}
				</div>
			</section>
		{/if}
		{#if r.products.total}
			<section>
				{@render head(
					m().search.productsSection,
					r.products.total,
					`/products?q=${encodeURIComponent(data.q)}`
				)}
				<div class="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-4">
					{#each r.products.items as product (product.id)}<ProductCard {product} />{/each}
				</div>
			</section>
		{/if}
		{#if r.services.total}
			<section>
				{@render head(
					m().search.servicesSection,
					r.services.total,
					`/services?q=${encodeURIComponent(data.q)}`
				)}
				<div class="grid gap-4 md:grid-cols-2">
					{#each r.services.items as service (service.id)}<ServiceCard {service} />{/each}
				</div>
			</section>
		{/if}
	{/if}
</div>
