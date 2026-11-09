<script lang="ts">
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import BadgeCheckIcon from '@lucide/svelte/icons/badge-check';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import LandmarkIcon from '@lucide/svelte/icons/landmark';
	import ShieldCheckIcon from '@lucide/svelte/icons/shield-check';
	import StoreIcon from '@lucide/svelte/icons/store';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import Picture from '#lib/components/app/Picture.svelte';
	import ProductCard from '#lib/components/app/ProductCard.svelte';
	import SearchPill from '#lib/components/app/SearchPill.svelte';
	import ServiceCard from '#lib/components/app/ServiceCard.svelte';
	import StoreCard from '#lib/components/app/StoreCard.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { fmt, m, pick } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const home = $derived(data.home);
	const s = $derived(home.settings);
	const isEmpty = $derived(
		!home.featured_stores.length &&
			!home.featured_products.length &&
			!home.popular_services.length &&
			!home.recent_stores.length
	);
	const promises = $derived([
		{ icon: LandmarkIcon, title: m().home.promise1Title, body: m().home.promise1Body },
		{ icon: ShieldCheckIcon, title: m().home.promise2Title, body: m().home.promise2Body },
		{ icon: BadgeCheckIcon, title: m().home.promise3Title, body: m().home.promise3Body }
	]);
	const topCategories = $derived(home.categories.filter((c) => !c.parent_id));

	/*
	 * Hero constellation: up to five featured products float above the headline,
	 * largest in the centre, smaller and tilted toward the edges, slightly overlapping.
	 */
	const slots = [
		{
			size: 'w-28 sm:w-36',
			offset: 'translate-y-10',
			tilt: '-rotate-6',
			show: 'hidden sm:block',
			delay: '0s'
		},
		{ size: 'w-32 sm:w-44', offset: 'translate-y-2', tilt: '-rotate-2', show: '', delay: '-2.5s' },
		{
			size: 'w-36 sm:w-52',
			offset: '-translate-y-2',
			tilt: 'rotate-0',
			show: '',
			delay: '-1s',
			z: 'z-10'
		},
		{ size: 'w-32 sm:w-44', offset: 'translate-y-4', tilt: 'rotate-3', show: '', delay: '-3.5s' },
		{
			size: 'w-28 sm:w-36',
			offset: 'translate-y-12',
			tilt: 'rotate-6',
			show: 'hidden sm:block',
			delay: '-5s'
		}
	];
	// Product i lands in slot centreOut[i], so the first (most featured) one takes the centre.
	const centreOut = [2, 1, 3, 0, 4];
	const constellation = $derived(
		home.featured_products
			.filter((p) => p.images.length)
			.slice(0, 5)
			.map((product, i) => ({ product, at: centreOut[i] }))
			.sort((a, b) => a.at - b.at)
			.map(({ product, at }) => ({ product, slot: slots[at] }))
	);
</script>

<svelte:head>
	<title>{m().brand.name} · {m().brand.tagline}</title>
</svelte:head>

<!-- Section header: 20px semibold with a chevron affordance; the whole title is the link. -->
{#snippet sectionHead(title: string, href?: string, id?: string)}
	<div class="mb-6 flex items-center justify-between gap-4">
		{#if href}
			<h2 {id} class="type-title text-ink">
				<a
					{href}
					class="group/head inline-flex items-center gap-1 rounded-full focus-visible:ring-4 focus-visible:ring-ring/20 focus-visible:outline-none"
				>
					{title}
					<ChevronRightIcon
						class="rtl-flip size-5 transition-transform duration-200 group-hover/head:translate-x-0.5 rtl:group-hover/head:-translate-x-0.5"
						aria-hidden="true"
					/>
				</a>
			</h2>
			<Button
				{href}
				variant="outline"
				size="sm"
				class="hidden sm:inline-flex"
				tabindex={-1}
				aria-hidden="true"
			>
				{m().common.viewAll}
			</Button>
		{:else}
			<h2 {id} class="type-title text-ink">{title}</h2>
		{/if}
	</div>
{/snippet}

<!-- ─── Hero ─────────────────────────────────────────────────────────────── -->
<section class="relative overflow-hidden">
	<div class="container-page flex flex-col items-center pt-32 pb-4 text-center sm:pb-6">
		{#if constellation.length >= 3}
			<ul
				class="mb-10 flex items-start justify-center sm:mb-14"
				aria-label={m().home.featuredProducts}
			>
				{#each constellation as { slot, product } (product.id)}
					<li class={cn('-mx-2 shrink-0 sm:-mx-3', slot.show, slot.z)}>
						<a
							href="/products/{product.id}"
							class={cn(
								'group block rounded-[24px] bg-card p-1.5 text-start shadow-soft ring-1 ring-edge transition-shadow duration-300 hover:shadow-lift focus-visible:ring-4 focus-visible:ring-ring/25 focus-visible:outline-none',
								'animate-[drift_9s_ease-in-out_infinite]',
								slot.size,
								slot.offset,
								slot.tilt
							)}
							style="animation-delay: {slot.delay}"
						>
							<div class="aspect-square overflow-hidden rounded-[18px] bg-surface-2">
								<Picture
									src={product.images[0]?.url}
									alt={product.images[0]?.alt || product.title}
									fallback={product.title}
									loading="eager"
									class="transition-transform duration-700 group-hover:scale-[1.05]"
								/>
							</div>
							<div class="flex flex-col gap-0.5 px-1.5 pt-2 pb-1">
								<p class="truncate text-[0.8125rem] font-semibold tracking-[-0.02em] text-ink">
									<bdi>{product.store.name}</bdi>
								</p>
								<p class="truncate type-caption text-ink-3 tabular">
									{fmt.money(product.discounted_price ?? product.price)}
								</p>
							</div>
						</a>
					</li>
				{/each}
			</ul>
		{/if}

		<h1 class="max-w-4xl font-display type-display text-ink">
			<bdi>{pick(s, 'hero_title')}</bdi>
		</h1>
		<p class="mt-5 max-w-xl text-base text-pretty text-ink-2 sm:text-lg">
			<bdi>{pick(s, 'hero_subtitle') || m().brand.tagline}</bdi>
		</p>

		<SearchPill size="lg" class="mt-8 max-w-xl" />

		{#if topCategories.length}
			<nav aria-label={m().home.categories} class="mt-6 w-full max-w-3xl">
				<!-- One swipeable row on phones; a centred wrapping row from sm up. -->
				<ul
					class="rail -mx-4 scroll-px-4 justify-start gap-2 px-4 py-1 sm:mx-0 sm:flex sm:flex-wrap sm:justify-center sm:overflow-visible sm:px-0"
				>
					{#each topCategories as c (c.id)}
						<li>
							<Button href="/products?category={c.slug}" variant="outline">
								<bdi>{pick(c, 'name')}</bdi>
							</Button>
						</li>
					{/each}
				</ul>
			</nav>
		{/if}

		<div class="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
			<Button href="/stores" variant="link" class="px-0">
				{m().home.heroCta}<ArrowRightIcon class="rtl-flip" data-icon="inline-end" />
			</Button>
			<Button href="/sell" variant="link" class="px-0 text-ink-2">
				<StoreIcon data-icon="inline-start" />{m().home.heroSecondary}
			</Button>
		</div>
	</div>
</section>

<!-- ─── Promotions: the image IS the card, display type set straight on it ── -->
{#if s.promotions?.length}
	<section class="container-page grid gap-3 md:grid-cols-5">
		{#each s.promotions as promo, i (i)}
			<a
				href={promo.link || '/products'}
				class={cn(
					'group relative flex min-h-56 flex-col overflow-hidden rounded-2xl p-7 focus-visible:ring-4 focus-visible:ring-ring/25 focus-visible:outline-none sm:min-h-72',
					promo.image_url ? 'bg-scrim text-on-scrim' : 'bg-surface-2 text-ink',
					s.promotions.length > 1 && i % 2 === 0 ? 'md:col-span-3' : 'md:col-span-2',
					s.promotions.length === 1 && 'md:col-span-5'
				)}
			>
				{#if promo.image_url}
					<img
						src={promo.image_url}
						alt=""
						class="absolute inset-0 size-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.04]"
					/>
					<div
						class="absolute inset-0 bg-gradient-to-b from-scrim/55 via-scrim/10 to-transparent"
					></div>
				{/if}
				<div class="relative flex max-w-md flex-col gap-2">
					<p class="font-display type-headline"><bdi>{pick(promo, 'title')}</bdi></p>
					{#if pick(promo, 'subtitle')}
						<p class="text-sm opacity-85"><bdi>{pick(promo, 'subtitle')}</bdi></p>
					{/if}
				</div>
				<span
					class="relative mt-auto inline-flex size-10 items-center justify-center self-end rounded-full bg-card text-ink shadow-float transition-transform duration-300 group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5"
					aria-hidden="true"
				>
					<ArrowRightIcon class="rtl-flip size-4" />
				</span>
			</a>
		{/each}
	</section>
{/if}

{#if isEmpty}
	<div class="container-page mt-16">
		<EmptyState icon={StoreIcon} title={m().home.emptyTitle} description={m().home.emptyBody}>
			<Button href="/sell">{m().home.heroSecondary}</Button>
		</EmptyState>
	</div>
{/if}

{#if home.featured_stores.length}
	<section class="container-page mt-20" aria-labelledby="featured-stores">
		{@render sectionHead(m().home.featuredStores, '/stores', 'featured-stores')}
		<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{#each home.featured_stores.slice(0, 6) as store (store.id)}
				<StoreCard {store} />
			{/each}
		</div>
	</section>
{/if}

{#if home.featured_products.length}
	<section class="container-page mt-20" aria-labelledby="featured-products">
		{@render sectionHead(m().home.featuredProducts, '/products', 'featured-products')}
		<div class="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
			{#each home.featured_products.slice(0, 8) as product (product.id)}
				<ProductCard {product} />
			{/each}
		</div>
	</section>
{/if}

<!-- ─── Trust band: neutral wash, mono icons — no colour competes with product ── -->
<section class="container-page mt-20">
	<div class="grid gap-10 rounded-2xl bg-surface-2 px-6 py-12 sm:px-10 md:grid-cols-3 md:gap-8">
		{#each promises as p (p.title)}
			<div class="flex flex-col gap-3">
				<span
					class="inline-flex size-11 items-center justify-center rounded-full bg-card text-ink shadow-pill"
				>
					<p.icon class="size-5" aria-hidden="true" />
				</span>
				<h3 class="type-title text-ink">{p.title}</h3>
				<p class="text-sm leading-relaxed text-ink-2">{p.body}</p>
			</div>
		{/each}
	</div>
</section>

{#if home.popular_services.length}
	<section class="container-page mt-20" aria-labelledby="popular-services">
		{@render sectionHead(m().home.popularServices, '/services', 'popular-services')}
		<div class="grid gap-3 md:grid-cols-2">
			{#each home.popular_services.slice(0, 6) as service (service.id)}
				<ServiceCard {service} />
			{/each}
		</div>
	</section>
{/if}

{#if home.recent_stores.length}
	<section class="container-page mt-20" aria-labelledby="recent-stores">
		{@render sectionHead(m().home.recentStores, '/stores?sort=newest', 'recent-stores')}
		<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{#each home.recent_stores.slice(0, 3) as store (store.id)}
				<StoreCard {store} />
			{/each}
		</div>
	</section>
{/if}

{#if s.testimonials?.length}
	<section class="container-page mt-20" aria-labelledby="testimonials">
		{@render sectionHead(m().home.testimonials, undefined, 'testimonials')}
		<div class="grid gap-3 md:grid-cols-3">
			{#each s.testimonials as t, i (i)}
				<Card.Root>
					<figure class="contents">
						<Card.Content class="flex-1">
							<blockquote class="text-lg leading-relaxed tracking-[-0.02em] text-ink">
								“<bdi>{pick(t, 'quote')}</bdi>”
							</blockquote>
						</Card.Content>
						<Card.Content>
							<figcaption class="type-label text-ink-3"><bdi>{t.name}</bdi></figcaption>
						</Card.Content>
					</figure>
				</Card.Root>
			{/each}
		</div>
	</section>
{/if}
