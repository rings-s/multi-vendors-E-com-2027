<script lang="ts">
	import ClockIcon from '@lucide/svelte/icons/clock';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import AddToCart from '#lib/components/app/AddToCart.svelte';
	import Gallery from '#lib/components/app/Gallery.svelte';
	import StoreLinkItem from '#lib/components/app/StoreLinkItem.svelte';
	import PriceTag from '#lib/components/app/PriceTag.svelte';
	import * as Breadcrumb from '#lib/components/ui/breadcrumb/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const s = $derived(data.service);
	const where = $derived(
		s.location_type === 'AT_CUSTOMER'
			? m().catalog.locationAtCustomer
			: s.location_type === 'ONLINE'
				? m().catalog.locationOnline
				: m().catalog.locationAtStore
	);
	const bookable = $derived(s.availability === 'AVAILABLE');
</script>

<svelte:head><title>{s.title} · {s.store.name}</title></svelte:head>

<div class="container-page py-8">
	<Breadcrumb.Root class="mb-6">
		<Breadcrumb.List>
			<Breadcrumb.Item
				><Breadcrumb.Link href="/services">{m().nav.services}</Breadcrumb.Link></Breadcrumb.Item
			>
			<Breadcrumb.Separator />
			<Breadcrumb.Item
				><Breadcrumb.Link href="/stores/{s.store.slug}?tab=services"
					><bdi>{s.store.name}</bdi></Breadcrumb.Link
				></Breadcrumb.Item
			>
			<Breadcrumb.Separator />
			<Breadcrumb.Item
				><Breadcrumb.Page class="line-clamp-1"><bdi>{s.title}</bdi></Breadcrumb.Page
				></Breadcrumb.Item
			>
		</Breadcrumb.List>
	</Breadcrumb.Root>

	<div class="grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-16">
		<Gallery images={s.images} title={s.title} />
		<div class="flex flex-col gap-8 lg:sticky lg:top-24 lg:self-start">
			<div class="flex flex-col gap-4">
				<a href="/stores/{s.store.slug}" class="self-start text-sm text-ink-3 hover:text-ink"
					><bdi>{s.store.name}</bdi></a
				>
				<h1 class="font-display text-3xl leading-tight text-ink sm:text-4xl">
					<bdi>{s.title}</bdi>
				</h1>
				<PriceTag price={s.price} discounted={s.discounted_price} size="lg" />
			</div>
			<Card.Root size="sm">
				<Card.Content>
					<dl class="grid grid-cols-2 gap-4">
						<div class="flex flex-col gap-1">
							<dt class="flex items-center gap-1.5 text-ink-3">
								<ClockIcon class="size-4" aria-hidden="true" />{m().catalog.duration}
							</dt>
							<dd class="font-medium text-ink">{m().common.minutes({ n: s.duration_minutes })}</dd>
						</div>
						<div class="flex flex-col gap-1">
							<dt class="flex items-center gap-1.5 text-ink-3">
								<MapPinIcon class="size-4" aria-hidden="true" />{m().catalog.location}
							</dt>
							<dd class="font-medium text-ink">{where}</dd>
							{#if s.location}<dd class="text-ink-2">{s.location}</dd>{/if}
						</div>
					</dl>
				</Card.Content>
			</Card.Root>
			{#if !bookable}<p class="text-sm text-ink-3">{m().catalog.unavailable}</p>{/if}
			<AddToCart
				item={{ service_id: s.id, quantity: 1 }}
				disabled={!bookable}
				label={m().catalog.bookService}
			/>
			<Separator />
			<section class="flex flex-col gap-3">
				<h2 class="font-medium text-ink">{m().catalog.description}</h2>
				<div class="leading-relaxed whitespace-pre-line text-ink-2">
					<bdi>{s.description || '—'}</bdi>
				</div>
			</section>
			<StoreLinkItem store={s.store} />
		</div>
	</div>
</div>
