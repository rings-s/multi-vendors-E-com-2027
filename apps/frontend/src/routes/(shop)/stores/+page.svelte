<script lang="ts">
	import StoreIcon from '@lucide/svelte/icons/store';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StoreCard from '#lib/components/app/StoreCard.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { m, pick } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const f = $derived(data.filters);
</script>

<svelte:head><title>{m().stores.title} · {m().brand.name}</title></svelte:head>

<div class="container-page flex flex-col gap-8 py-12">
	<PageHeader title={m().stores.title} description={m().stores.subtitle} size="lg" />

	<FilterBar>
		<Field.Field class="min-w-52 flex-1">
			<Field.Label for="f-q">{m().common.search}</Field.Label>
			<Input
				id="f-q"
				name="q"
				type="search"
				value={f.q}
				placeholder={m().stores.searchPlaceholder}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="f-cat">{m().stores.category}</Field.Label>
			<NativeSelect.Root id="f-cat" name="category" value={f.category}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				{#each data.categories as c (c.id)}
					<NativeSelect.Option value={c.slug}>{pick(c, 'name')}</NativeSelect.Option>
				{/each}
			</NativeSelect.Root>
		</Field.Field>
		<Field.Field class="w-36">
			<Field.Label for="f-city">{m().stores.city}</Field.Label>
			<Input id="f-city" name="city" value={f.city} placeholder={m().stores.anyCity} />
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="f-rating">{m().stores.rating}</Field.Label>
			<NativeSelect.Root id="f-rating" name="min_rating" value={f.min_rating}>
				<NativeSelect.Option value="">{m().stores.anyRating}</NativeSelect.Option>
				{#each [4, 3, 2] as n (n)}
					<NativeSelect.Option value={String(n)}
						>{m().stores.ratingAtLeast({ n })}</NativeSelect.Option
					>
				{/each}
			</NativeSelect.Root>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="f-sort">{m().common.sortBy}</Field.Label>
			<NativeSelect.Root id="f-sort" name="sort" value={f.sort}>
				<NativeSelect.Option value="popular">{m().stores.sortPopular}</NativeSelect.Option>
				<NativeSelect.Option value="newest">{m().stores.sortNewest}</NativeSelect.Option>
				<NativeSelect.Option value="rating">{m().stores.sortRating}</NativeSelect.Option>
			</NativeSelect.Root>
		</Field.Field>
	</FilterBar>

	{#if data.stores.items.length}
		<div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
			{#each data.stores.items as store (store.id)}
				<StoreCard {store} />
			{/each}
		</div>
		<Paginator total={data.stores.total} page={data.stores.page} pageSize={data.stores.page_size} />
	{:else}
		<EmptyState icon={StoreIcon} title={m().stores.emptyTitle} description={m().stores.emptyBody} />
	{/if}
</div>
