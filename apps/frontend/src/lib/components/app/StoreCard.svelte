<script lang="ts">
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import type { Store } from '#lib/api/types.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import Picture from './Picture.svelte';
	import RatingStars from './RatingStars.svelte';

	let { store }: { store: Store } = $props();
</script>

<!-- A store is a business, not a listing: cover, its own logo, name, place and rating. -->
<a
	href="/stores/{store.slug}"
	class="group flex h-full flex-col overflow-hidden rounded-2xl bg-card ring-1 ring-edge transition-shadow duration-200 outline-none hover:shadow-lift focus-visible:ring-2 focus-visible:ring-ring"
	data-testid="store-card"
>
	<div class="relative aspect-[5/2] overflow-hidden bg-surface-3">
		<Picture
			src={store.cover_url}
			alt=""
			fallback={store.name}
			class="transition-transform duration-500 ease-(--ease-out) group-hover:scale-[1.04] [&>span]:hidden"
		/>
		{#if !store.is_open}
			<span
				class="absolute end-2 top-2 rounded-md bg-card/95 px-2 py-1 text-xs font-medium text-ink shadow-pill"
			>
				{m().stores.closedNow}
			</span>
		{/if}
	</div>
	<div class="flex flex-1 flex-col gap-3 p-4 pt-0">
		<div class="flex items-end gap-3">
			<div
				class="relative -mt-7 size-14 shrink-0 overflow-hidden rounded-xl bg-card shadow-soft ring-4 ring-card"
			>
				<Picture src={store.logo_url} alt="" fallback={store.name} />
			</div>
			<div class="flex min-w-0 flex-1 flex-col pt-3">
				<h3 class="truncate text-base font-semibold text-ink"><bdi>{store.name}</bdi></h3>
				<span class="inline-flex items-center gap-1 text-[0.8125rem] text-ink-3">
					<MapPinIcon class="size-3.5 shrink-0" aria-hidden="true" />
					<span class="truncate">{store.city || fmt.region(store.region)}</span>
				</span>
			</div>
		</div>
		{#if store.description}
			<p class="line-clamp-2 text-sm leading-relaxed text-ink-2"><bdi>{store.description}</bdi></p>
		{/if}
		<RatingStars rating={store.rating_avg} count={store.rating_count} class="mt-auto" />
	</div>
</a>
