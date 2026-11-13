<script lang="ts">
	import { page } from '$app/state';
	import MailIcon from '@lucide/svelte/icons/mail';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import PackageIcon from '@lucide/svelte/icons/package';
	import PhoneIcon from '@lucide/svelte/icons/phone';
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import StarIcon from '@lucide/svelte/icons/star';
	import TruckIcon from '@lucide/svelte/icons/truck';
	import ArrowUpRightIcon from '@lucide/svelte/icons/arrow-up-right';
	import StoreIcon from '@lucide/svelte/icons/store';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import LocationMap, { type MapPin } from '#lib/components/app/LocationMap.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import Picture from '#lib/components/app/Picture.svelte';
	import ProductCard from '#lib/components/app/ProductCard.svelte';
	import RatingStars from '#lib/components/app/RatingStars.svelte';
	import ServiceCard from '#lib/components/app/ServiceCard.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { etaRange } from '#lib/delivery.js';
	import { fmt, locale, m, pick } from '#lib/i18n/state.svelte.js';
	import { goto } from '$app/navigation';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const store = $derived(data.store);
	const storeCategories = $derived(
		data.categories.filter((c) => store.category_ids?.includes(c.id))
	);

	const tabs = $derived([
		{ key: 'products', label: m().stores.products, count: data.products.total },
		{ key: 'services', label: m().stores.services, count: data.services.total },
		{ key: 'reviews', label: m().stores.reviewsTab, count: store.rating_count },
		{ key: 'about', label: m().stores.about, count: null }
	]);

	type PickupPoint = (typeof data.locations)[number];
	const zones = $derived(data.delivery?.zones ?? []);
	const minFee = $derived(zones.length ? Math.min(...zones.map((z) => z.fee)) : 0);
	const thresholds = $derived(
		zones.map((z) => z.free_delivery_threshold).filter((t): t is number => t != null)
	);
	const minThreshold = $derived(thresholds.length ? Math.min(...thresholds) : null);
	const pickupPins = $derived<MapPin[]>(
		data.locations.flatMap((l) =>
			l.latitude != null && l.longitude != null
				? [{ id: l.id, lat: l.latitude, lng: l.longitude, label: l.label || l.city }]
				: []
		)
	);
	const addressParts = (l: PickupPoint) => [
		l.building_number,
		l.street,
		l.district,
		l.city,
		fmt.region(l.region),
		l.postal_code
	];
	const addressLine = (l: PickupPoint) => fmt.list(addressParts(l));
	/** OpenStreetMap directions to a pin, or an address search when the point has no pin. */
	const mapLink = (l: PickupPoint) =>
		l.latitude != null && l.longitude != null
			? `https://www.openstreetmap.org/directions?to=${l.latitude}%2C${l.longitude}#map=17/${l.latitude}/${l.longitude}`
			: `https://www.openstreetmap.org/search?query=${encodeURIComponent(addressParts(l).filter(Boolean).join(', '))}`;

	function tabHref(key: string) {
		return key === 'products' ? `/stores/${store.slug}` : `/stores/${store.slug}?tab=${key}`;
	}

	function setSort(e: Event) {
		const url = new URL(page.url.href);
		url.searchParams.set('sort', (e.currentTarget as HTMLSelectElement).value);
		url.searchParams.delete('page');
		void goto(url);
	}
</script>

<svelte:head>
	<title>{store.name} · {m().brand.name}</title>
	<meta name="description" content={store.description} />
</svelte:head>

<section class="border-b border-line">
	<div class="container-page pt-3 sm:pt-5">
		<div class="relative h-48 overflow-hidden rounded-2xl bg-surface-2 sm:h-64 lg:h-80">
			<Picture src={store.cover_url} alt="" fallback={store.name} loading="eager" />
		</div>
	</div>
	<div class="container-page">
		<div class="relative z-10 flex flex-col gap-6 pb-8 sm:flex-row sm:items-end sm:justify-between">
			<div class="flex items-end gap-5">
				<div
					class="ms-4 -mt-12 size-24 shrink-0 overflow-hidden rounded-2xl border-4 border-background bg-surface shadow-lift sm:ms-6 sm:-mt-14 sm:size-28"
				>
					<Picture
						src={store.logo_url}
						alt="{store.name} logo"
						fallback={store.name}
						loading="eager"
					/>
				</div>
				<div class="flex flex-col gap-1.5 pt-4 pb-1">
					<h1 class="font-display type-headline text-ink"><bdi>{store.name}</bdi></h1>
					<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2">
						<span class="inline-flex items-center gap-1"
							><MapPinIcon class="size-4" aria-hidden="true" />{fmt.list([
								store.city,
								fmt.region(store.region)
							])}</span
						>
						<RatingStars rating={store.rating_avg} count={store.rating_count} />
						<span class="tabular">{m().stores.orders({ n: store.orders_count })}</span>
					</div>
				</div>
			</div>
			<div class="flex flex-wrap gap-2 text-sm">
				<Badge variant={store.is_open ? 'success' : 'secondary'}>
					<span class="size-1.5 rounded-full bg-current" aria-hidden="true"></span>{store.is_open
						? m().stores.openNow
						: m().stores.closedNow}
				</Badge>
				{#if data.delivery?.delivery_offered}
					<Badge href="/stores/{store.slug}?tab=about#delivery" variant="secondary">
						<TruckIcon data-icon="inline-start" aria-hidden="true" />
						{#if minFee === 0}
							{m().stores.freeShipping}
						{:else if minThreshold != null}
							{m().delivery.freeOver({ amount: fmt.money(minThreshold) })}
						{:else}
							{m().delivery.fee}: {fmt.money(minFee)}
						{/if}
					</Badge>
				{/if}
				{#if data.locations.length}
					<Badge href="/stores/{store.slug}?tab=about#pickup" variant="outline">
						<StoreIcon data-icon="inline-start" aria-hidden="true" />{m().stores.pickupAvailable}
					</Badge>
				{/if}
			</div>
		</div>
		{#if !store.is_open}
			<Alert.Root class="mb-6">
				<Alert.Title>{m().stores.closedNow}</Alert.Title>
				<Alert.Description>{m().stores.closedNotice}</Alert.Description>
			</Alert.Root>
		{/if}
		<!-- Each tab is a real link (the tab lives in the URL), styled by the line Tabs variant. -->
		<Tabs.Root value={data.tab} activationMode="manual" class="overflow-x-auto pb-1.5">
			<Tabs.List variant="line" aria-label={store.name}>
				{#each tabs as t (t.key)}
					<Tabs.Trigger value={t.key}>
						{#snippet child({ props })}
							<a
								{...props}
								href={tabHref(t.key)}
								aria-current={data.tab === t.key ? 'page' : undefined}
							>
								{t.label}
								{#if t.count != null}<span class="text-xs text-ink-3 tabular"
										>{fmt.number(t.count)}</span
									>{/if}
							</a>
						{/snippet}
					</Tabs.Trigger>
				{/each}
			</Tabs.List>
		</Tabs.Root>
	</div>
</section>

<div class="container-page py-10">
	{#if data.tab === 'products'}
		{#if data.products.items.length}
			<div class="mb-6 flex justify-end">
				<Field.Field orientation="horizontal" class="w-auto">
					<Field.Label for="store-sort" class="font-normal">{m().common.sortBy}</Field.Label>
					<NativeSelect.Root id="store-sort" value={data.sort} onchange={setSort} size="sm">
						<NativeSelect.Option value="newest">{m().catalog.sortNewest}</NativeSelect.Option>
						<NativeSelect.Option value="price_asc">{m().catalog.sortPriceAsc}</NativeSelect.Option>
						<NativeSelect.Option value="price_desc">{m().catalog.sortPriceDesc}</NativeSelect.Option
						>
					</NativeSelect.Root>
				</Field.Field>
			</div>
			<div class="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-3 lg:grid-cols-4">
				{#each data.products.items as product (product.id)}
					<ProductCard {product} showStore={false} />
				{/each}
			</div>
			<Paginator
				total={data.products.total}
				page={data.products.page}
				pageSize={data.products.page_size}
			/>
		{:else}
			<EmptyState icon={PackageIcon} title={m().stores.noProducts} />
		{/if}
	{:else if data.tab === 'services'}
		{#if data.services.items.length}
			<div class="grid gap-4 md:grid-cols-2">
				{#each data.services.items as service (service.id)}
					<ServiceCard {service} showStore={false} />
				{/each}
			</div>
			<Paginator
				total={data.services.total}
				page={data.services.page}
				pageSize={data.services.page_size}
			/>
		{:else}
			<EmptyState icon={SparklesIcon} title={m().stores.noServices} />
		{/if}
	{:else if data.tab === 'reviews'}
		{#await data.reviews}
			<div class="flex max-w-3xl flex-col gap-6" role="status">
				{#each [1, 2, 3] as i (i)}
					<div class="flex flex-col gap-2">
						<Skeleton class="h-4 w-40" /><Skeleton class="h-4 w-full" /><Skeleton
							class="h-4 w-2/3"
						/>
					</div>
				{/each}
			</div>
		{:then reviews}
			{#if reviews.items.length}
				<Item.Group class="max-w-3xl gap-0">
					{#each reviews.items as r, i (r.id)}
						{#if i > 0}<Item.Separator class="my-0" />{/if}
						<Item.Root role="listitem" class="px-0 py-6 first:pt-0">
							<Item.Content>
								<Item.Title><bdi>{r.customer_name}</bdi></Item.Title>
								<RatingStars rating={r.rating} />
								{#if r.comment}<p class="text-base leading-relaxed text-ink-2">
										<bdi>{r.comment}</bdi>
									</p>{/if}
							</Item.Content>
							<Item.Actions class="self-start">
								<time class="text-xs text-ink-3" datetime={r.created_at}
									>{fmt.date(r.created_at)}</time
								>
							</Item.Actions>
						</Item.Root>
					{/each}
				</Item.Group>
				<Paginator total={reviews.total} page={reviews.page} pageSize={reviews.page_size} />
			{:else}
				<EmptyState icon={StarIcon} title={m().stores.noReviews} />
			{/if}
		{:catch}
			<Alert.Root variant="destructive"
				><Alert.Description>{m().errors.generic}</Alert.Description></Alert.Root
			>
		{/await}
	{:else}
		<div class="grid gap-10 lg:grid-cols-[2fr_1fr]">
			<div class="flex flex-col gap-8">
				<section class="flex flex-col gap-3">
					<h2 class="type-title">{m().stores.about}</h2>
					<p class="leading-relaxed whitespace-pre-line text-ink-2">
						<bdi>{store.description || m().stores.noPolicy}</bdi>
					</p>
					{#if storeCategories.length}
						<ul class="flex flex-wrap gap-2 pt-2">
							{#each storeCategories as c (c.id)}
								<li>
									<Badge href="/products?category={c.slug}" variant="secondary"
										><bdi>{pick(c, 'name')}</bdi></Badge
									>
								</li>
							{/each}
						</ul>
					{/if}
				</section>
				<Separator />
				<section class="grid gap-8 sm:grid-cols-2">
					<div class="flex flex-col gap-2">
						<h3 class="font-medium text-ink">{m().delivery.policy}</h3>
						<p class="text-sm leading-relaxed whitespace-pre-line text-ink-2">
							<bdi
								>{data.delivery?.delivery_policy ||
									store.shipping_policy ||
									m().stores.noPolicy}</bdi
							>
						</p>
					</div>
					<div class="flex flex-col gap-2">
						<h3 class="font-medium text-ink">{m().stores.returnPolicy}</h3>
						<p class="text-sm leading-relaxed whitespace-pre-line text-ink-2">
							<bdi>{store.return_policy || m().stores.noPolicy}</bdi>
						</p>
					</div>
				</section>
				{#if data.delivery}
					<Separator />
					<section
						id="delivery"
						class="flex scroll-mt-24 flex-col gap-4"
						aria-labelledby="delivery-title"
					>
						<h2 id="delivery-title" class="type-title">{m().delivery.storeAreas}</h2>
						{#if data.delivery.zones.length}
							<ul class="grid gap-3 sm:grid-cols-2">
								{#each data.delivery.zones as z, i (i)}
									<li class="flex flex-col gap-1 rounded-xl border border-line p-4 text-sm">
										<p class="flex justify-between gap-3 font-medium text-ink">
											<span><bdi>{z.name}</bdi></span>
											<span class="tabular"
												>{z.fee === 0 ? m().delivery.free : fmt.money(z.fee)}</span
											>
										</p>
										<p class="text-ink-2">
											{z.region
												? [fmt.region(z.region), fmt.list(z.cities)].filter(Boolean).join(' · ')
												: m().delivery.allSaudi}
										</p>
										{#if z.districts.length}<p class="text-ink-3">{fmt.list(z.districts)}</p>{/if}
										<p class="text-ink-3">
											{m().delivery.eta({
												range: etaRange(z.eta_min_minutes, z.eta_max_minutes, locale())
											})}
										</p>
										{#if z.free_delivery_threshold != null && z.fee > 0}
											<p class="text-success">
												{m().delivery.freeOver({ amount: fmt.money(z.free_delivery_threshold) })}
											</p>
										{/if}
									</li>
								{/each}
							</ul>
						{:else}
							<p class="text-sm text-ink-2">{m().delivery.storeNoDelivery}</p>
						{/if}
					</section>
				{/if}
				{#if data.locations.length}
					<Separator />
					<section
						id="pickup"
						class="flex scroll-mt-24 flex-col gap-4"
						aria-labelledby="pickup-title"
					>
						<div class="flex flex-col gap-1">
							<h2 id="pickup-title" class="type-title">{m().stores.pickupPoints}</h2>
							<p class="text-sm text-ink-2">{m().stores.pickupHint}</p>
						</div>
						{#if pickupPins.length}
							<LocationMap label={m().stores.pickupMap} pins={pickupPins} />
						{/if}
						<ul class="grid gap-3 sm:grid-cols-2">
							{#each data.locations as l (l.id)}
								<li>
									<Card.Root size="sm" class="h-full">
										<Card.Header>
											<Card.Title role="heading" aria-level={3} class="flex items-center gap-1.5">
												<MapPinIcon class="size-4 shrink-0 text-ink-3" aria-hidden="true" />
												{l.label || l.city}
											</Card.Title>
											<Card.Description>{addressLine(l)}</Card.Description>
										</Card.Header>
										<Card.Footer class="mt-auto border-0 bg-transparent pt-0">
											<a
												href={mapLink(l)}
												target="_blank"
												rel="noopener noreferrer"
												class="inline-flex items-center gap-1 text-sm font-medium text-ink underline decoration-foreground/25 underline-offset-4 hover:decoration-foreground"
											>
												{l.latitude != null ? m().stores.directions : m().stores.findOnMap}
												<ArrowUpRightIcon class="rtl-flip size-3.5" aria-hidden="true" />
												<span class="sr-only">({l.label || l.city})</span>
											</a>
										</Card.Footer>
									</Card.Root>
								</li>
							{/each}
						</ul>
					</section>
				{/if}
			</div>
			<aside class="h-fit">
				<Card.Root class="h-full">
					<Card.Header>
						<Card.Title role="heading" aria-level={2}>{m().stores.contact}</Card.Title>
					</Card.Header>
					<Card.Content class="flex flex-col gap-4 text-sm">
						<dl class="flex flex-col gap-3 text-ink-2">
							<div class="flex gap-2">
								<dt class="sr-only">{m().stores.location}</dt>
								<MapPinIcon class="size-4 shrink-0" aria-hidden="true" />
								<dd>{fmt.list([store.city, fmt.region(store.region)])}</dd>
							</div>
							{#if store.contact_email}
								<div class="flex gap-2">
									<dt class="sr-only">Email</dt>
									<MailIcon class="size-4 shrink-0" aria-hidden="true" />
									<dd>
										<a class="hover:text-ink" href="mailto:{store.contact_email}" dir="ltr"
											>{store.contact_email}</a
										>
									</dd>
								</div>
							{/if}
							{#if store.contact_phone}
								<div class="flex gap-2">
									<dt class="sr-only">{m().auth.phone}</dt>
									<PhoneIcon class="size-4 shrink-0" aria-hidden="true" />
									<dd>
										<a class="tabular hover:text-ink" href="tel:{store.contact_phone}" dir="ltr"
											>{fmt.phone(store.contact_phone)}</a
										>
									</dd>
								</div>
							{/if}
						</dl>
						<Separator />
						<p class="text-xs text-ink-3">
							{m().stores.since({ date: fmt.date(store.created_at) })}
						</p>
					</Card.Content>
				</Card.Root>
			</aside>
		</div>
	{/if}
</div>
