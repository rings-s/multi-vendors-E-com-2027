<script lang="ts">
	import ClockIcon from '@lucide/svelte/icons/clock';
	import type { Service } from '#lib/api/types.js';
	import { m, statusLabel } from '#lib/i18n/state.svelte.js';
	import Picture from './Picture.svelte';
	import PriceTag from './PriceTag.svelte';

	let { service, showStore = true }: { service: Service; showStore?: boolean } = $props();
	const image = $derived(service.images[0]);
</script>

<a
	href="/services/{service.id}"
	class="group flex h-full gap-4 rounded-2xl bg-card p-3 ring-1 ring-edge transition-shadow duration-200 outline-none hover:shadow-lift focus-visible:ring-2 focus-visible:ring-ring"
	data-testid="service-card"
>
	<div class="size-24 shrink-0 overflow-hidden rounded-xl bg-surface-2 sm:size-28">
		<Picture
			src={image?.url}
			alt={image?.alt || service.title}
			fallback={service.title}
			class="transition-transform duration-500 ease-(--ease-out) group-hover:scale-[1.04]"
		/>
	</div>
	<div class="flex min-w-0 flex-1 flex-col justify-between gap-2 py-1 pe-1">
		<div class="flex flex-col gap-1">
			{#if showStore}
				<p class="truncate text-[0.8125rem] text-ink-3"><bdi>{service.store.name}</bdi></p>
			{/if}
			<h3 class="line-clamp-2 text-[0.9375rem] leading-snug font-medium text-ink">
				<bdi>{service.title}</bdi>
			</h3>
		</div>
		<div class="flex flex-wrap items-center justify-between gap-2">
			<PriceTag price={service.price} discounted={service.discounted_price} size="sm" />
			<span class="inline-flex items-center gap-1 text-xs text-ink-3">
				<ClockIcon class="size-3.5" aria-hidden="true" />
				{m().common.minutes({ n: service.duration_minutes })} · {statusLabel(service.location_type)}
			</span>
		</div>
	</div>
</a>
