<script lang="ts">
	import type { Category } from '#lib/api/types.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { m, pick } from '#lib/i18n/state.svelte.js';
	import FilterBar from './FilterBar.svelte';

	interface Props {
		filters: {
			q: string;
			category: string;
			city: string;
			sort: string;
			min_price?: string;
			max_price?: string;
		};
		categories: Category[];
		kind: 'PRODUCT' | 'SERVICE';
	}

	let { filters: f, categories, kind }: Props = $props();
	const cats = $derived(
		categories.filter((c) => c.is_active && (c.kind === kind || c.kind === 'BOTH'))
	);
</script>

<FilterBar>
	<Field.Field class="min-w-52 flex-1">
		<Field.Label for="f-q">{m().common.search}</Field.Label>
		<Input id="f-q" name="q" type="search" value={f.q} placeholder={m().common.searchPlaceholder} />
	</Field.Field>
	<Field.Field class="w-auto">
		<Field.Label for="f-cat">{m().stores.category}</Field.Label>
		<NativeSelect.Root id="f-cat" name="category" value={f.category}>
			<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
			{#each cats as c (c.id)}
				<NativeSelect.Option value={c.slug}>{pick(c, 'name')}</NativeSelect.Option>
			{/each}
		</NativeSelect.Root>
	</Field.Field>
	<Field.Field class="w-32">
		<Field.Label for="f-city">{m().stores.city}</Field.Label>
		<Input id="f-city" name="city" value={f.city} placeholder={m().stores.anyCity} />
	</Field.Field>
	{#if kind === 'PRODUCT'}
		<Field.Field class="w-28">
			<Field.Label for="f-min">{m().catalog.minPrice}</Field.Label>
			<Input id="f-min" name="min_price" inputmode="decimal" value={f.min_price} dir="ltr" />
		</Field.Field>
		<Field.Field class="w-28">
			<Field.Label for="f-max">{m().catalog.maxPrice}</Field.Label>
			<Input id="f-max" name="max_price" inputmode="decimal" value={f.max_price} dir="ltr" />
		</Field.Field>
	{/if}
	<Field.Field class="w-auto">
		<Field.Label for="f-sort">{m().common.sortBy}</Field.Label>
		<NativeSelect.Root id="f-sort" name="sort" value={f.sort}>
			<NativeSelect.Option value="newest">{m().catalog.sortNewest}</NativeSelect.Option>
			<NativeSelect.Option value="popular">{m().catalog.sortPopular}</NativeSelect.Option>
			<NativeSelect.Option value="price_asc">{m().catalog.sortPriceAsc}</NativeSelect.Option>
			<NativeSelect.Option value="price_desc">{m().catalog.sortPriceDesc}</NativeSelect.Option>
		</NativeSelect.Root>
	</Field.Field>
</FilterBar>
