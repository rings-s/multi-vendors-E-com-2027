<script lang="ts">
	import ClockIcon from '@lucide/svelte/icons/clock';
	import type { Service } from '#lib/api/types.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { m, statusLabel } from '#lib/i18n/state.svelte.js';
	import Picture from './Picture.svelte';
	import PriceTag from './PriceTag.svelte';

	let { service, showStore = true }: { service: Service; showStore?: boolean } = $props();
	const image = $derived(service.images[0]);
</script>

<a
	href="/services/{service.id}"
	class="group block rounded-2xl focus-visible:ring-4 focus-visible:ring-ring/25 focus-visible:outline-none"
	data-testid="service-card"
>
	<Card.Root
		size="sm"
		class="h-full flex-row gap-4 p-2 transition-[box-shadow,translate] duration-300 ease-out group-hover:-translate-y-0.5 group-hover:shadow-lift"
	>
		<div class="size-24 shrink-0 overflow-hidden rounded-[20px] bg-surface-2 sm:size-28">
			<Picture src={image?.url} alt={image?.alt || service.title} fallback={service.title} />
		</div>
		<div class="flex min-w-0 flex-1 flex-col justify-between gap-2 py-2 pe-2">
			<div class="flex flex-col gap-1">
				{#if showStore}
					<p class="truncate type-label text-ink-3"><bdi>{service.store.name}</bdi></p>
				{/if}
				<Card.Title role="heading" aria-level={3} class="line-clamp-2">{service.title}</Card.Title>
			</div>
			<div class="flex flex-wrap items-center justify-between gap-2">
				<PriceTag price={service.price} discounted={service.discounted_price} size="sm" />
				<span class="inline-flex items-center gap-1 text-xs text-ink-3">
					<ClockIcon class="size-3.5" aria-hidden="true" />
					{m().common.minutes({ n: service.duration_minutes })} · {statusLabel(
						service.location_type
					)}
				</span>
			</div>
		</div>
	</Card.Root>
</a>
