<script lang="ts">
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import type { Store } from '#lib/api/types.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import Picture from './Picture.svelte';
	import RatingStars from './RatingStars.svelte';

	let { store }: { store: Store } = $props();
</script>

<!--
	Brand spotlight: the cover image is the card. The store name sits in white display type
	over a dark scrim; the logo floats as a white tile. No chrome beyond the 28px radius.
-->
<a
	href="/stores/{store.slug}"
	class="group flex h-full flex-col rounded-2xl bg-card p-2 text-card-foreground shadow-soft ring-1 ring-edge transition-[box-shadow,translate] duration-300 ease-out hover:-translate-y-0.5 hover:shadow-lift focus-visible:ring-4 focus-visible:ring-ring/25 focus-visible:outline-none"
	data-testid="store-card"
>
	<div class="relative aspect-[4/3] overflow-hidden rounded-[20px] bg-surface-3">
		<Picture
			src={store.cover_url}
			alt=""
			fallback={store.name}
			class="transition-transform duration-700 ease-out group-hover:scale-[1.04]"
		/>
		<div
			class="pointer-events-none absolute inset-0 bg-gradient-to-t from-scrim/70 via-scrim/10 to-transparent"
			aria-hidden="true"
		></div>
		{#if !store.is_open}
			<Badge variant="outline" class="absolute end-2.5 top-2.5 shadow-pill">
				{m().stores.closedNow}
			</Badge>
		{/if}
		<div class="absolute inset-x-0 bottom-0 flex items-end gap-3 p-4 text-on-scrim">
			<div
				class="size-12 shrink-0 overflow-hidden rounded-[14px] bg-card shadow-soft ring-2 ring-on-scrim/90"
			>
				<Picture src={store.logo_url} alt="" fallback={store.name} />
			</div>
			<div class="flex min-w-0 flex-col gap-0.5">
				<h3 class="truncate font-display text-xl leading-tight"><bdi>{store.name}</bdi></h3>
				<span class="inline-flex items-center gap-1 type-label text-on-scrim/85">
					<MapPinIcon class="size-3.5" aria-hidden="true" />{store.city || fmt.region(store.region)}
				</span>
			</div>
		</div>
	</div>
	<div class="flex flex-1 flex-col gap-1.5 px-2 pt-3 pb-2">
		<RatingStars rating={store.rating_avg} count={store.rating_count} />
		{#if store.description}
			<p class="line-clamp-2 text-sm leading-relaxed text-ink-2"><bdi>{store.description}</bdi></p>
		{/if}
	</div>
</a>
