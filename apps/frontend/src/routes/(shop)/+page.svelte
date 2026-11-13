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
	import ServiceCard from '#lib/components/app/ServiceCard.svelte';
	import StoreCard from '#lib/components/app/StoreCard.svelte';
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
	/** The banner shows what is actually for sale: up to three featured products. */
	const spotlight = $derived(home.featured_products.slice(0, 3));
	/** Recently opened stores that are not already listed as featured. */
	const newStores = $derived(
		home.recent_stores.filter((r) => !home.featured_stores.some((f) => f.id === r.id)).slice(0, 3)
	);
</script>

<svelte:head>
	<title>{m().brand.name} · {m().brand.tagline}</title>
</svelte:head>

{#snippet sectionHead(title: string, href?: string, id?: string)}
	<div class="mb-5 flex items-end justify-between gap-4">
		<h2 {id} class="type-title text-ink">{title}</h2>
		{#if href}
			<a
				{href}
				class="group/all inline-flex shrink-0 items-center gap-0.5 rounded-sm text-sm font-medium text-primary outline-none hover:underline hover:underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring/60"
			>
				{m().common.viewAll}<span class="sr-only">: {title}</span>
				<ChevronRightIcon
					class="rtl-flip size-4 transition-transform duration-200 group-hover/all:translate-x-0.5 rtl:group-hover/all:-translate-x-0.5"
					aria-hidden="true"
				/>
			</a>
		{/if}
	</div>
{/snippet}

<!-- ─── Banner: the offer and the way in, beside products that are actually on sale ─── -->
<section class="container-page pt-5 sm:pt-6">
	<div
		class={cn(
			'grid overflow-hidden rounded-2xl bg-hero text-hero-foreground',
			spotlight.length && 'lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]'
		)}
	>
		<div class="flex flex-col justify-center gap-5 p-6 sm:p-10 lg:p-14">
			<h1 class="rise max-w-[16ch] type-display">
				<bdi>{pick(s, 'hero_title')}</bdi>
			</h1>
			<p class="rise max-w-md text-base text-pretty text-hero-muted sm:text-lg" style="--i: 1">
				<bdi>{pick(s, 'hero_subtitle') || m().brand.tagline}</bdi>
			</p>
			<div class="rise mt-2 flex flex-wrap items-center gap-3" style="--i: 2">
				<Button
					href="/stores"
					size="lg"
					class="bg-hero-foreground text-hero shadow-none hover:bg-hero-foreground/90 active:bg-hero-foreground/90"
				>
					{m().home.heroCta}<ArrowRightIcon class="rtl-flip" data-icon="inline-end" />
				</Button>
				<Button
					href="/sell"
					size="lg"
					variant="ghost"
					class="text-hero-foreground hover:bg-hero-foreground/10"
				>
					<StoreIcon data-icon="inline-start" />{m().home.heroSecondary}
				</Button>
			</div>
		</div>

		{#if spotlight.length}
			<ul
				class={cn(
					'grid content-center gap-3 p-4 pt-0 sm:p-6 sm:pt-0 lg:p-8 lg:ps-0',
					spotlight.length === 1
						? 'grid-cols-1'
						: spotlight.length === 2
							? 'grid-cols-2'
							: 'grid-cols-3 lg:grid-cols-[1.35fr_1fr] lg:grid-rows-2'
				)}
				aria-label={m().home.featuredProducts}
			>
				{#each spotlight as product, i (product.id)}
					<li
						class={cn('rise', spotlight.length === 3 && i === 0 && 'lg:row-span-2')}
						style="--i: {i + 2}"
					>
						<a
							href="/products/{product.id}"
							class="group relative block h-full min-h-32 overflow-hidden rounded-xl bg-surface-2 text-ink outline-none focus-visible:ring-2 focus-visible:ring-hero-foreground focus-visible:ring-offset-2 focus-visible:ring-offset-hero sm:min-h-44"
						>
							<div
								class={cn(
									'size-full',
									spotlight.length === 3 && i === 0
										? 'aspect-square lg:aspect-auto'
										: 'aspect-square'
								)}
							>
								<Picture
									src={product.images[0]?.url}
									alt={product.images[0]?.alt || product.title}
									fallback={product.title}
									loading="eager"
									class="transition-transform duration-500 ease-(--ease-out) group-hover:scale-[1.04]"
								/>
							</div>
							<div
								class="absolute inset-x-1.5 bottom-1.5 flex items-center justify-center gap-2 rounded-lg bg-card/95 px-2 py-1.5 shadow-soft sm:inset-x-2 sm:bottom-2 sm:justify-between sm:px-3 sm:py-2"
							>
								<p class="hidden min-w-0 truncate text-sm font-medium sm:block" dir="auto">
									{product.title}
								</p>
								<p class="shrink-0 text-xs font-semibold tabular sm:text-sm">
									{fmt.money(product.discounted_price ?? product.price)}
								</p>
							</div>
						</a>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</section>

<!-- ─── Categories ─────────────────────────────────────────────────────────── -->
{#if topCategories.length}
	<section class="container-page mt-10" aria-labelledby="home-categories">
		{@render sectionHead(m().home.categories, undefined, 'home-categories')}
		<ul
			class="rail -mx-4 scroll-px-4 auto-cols-[minmax(9.5rem,1fr)] px-4 sm:mx-0 sm:auto-cols-auto sm:grid-flow-row sm:grid-cols-3 sm:overflow-visible sm:px-0 lg:grid-cols-5"
		>
			{#each topCategories as c (c.id)}
				<li>
					<a
						href="/{c.kind === 'SERVICE' ? 'services' : 'products'}?category={c.slug}"
						class="group flex h-full items-center justify-between gap-3 rounded-xl bg-card px-4 py-3.5 ring-1 ring-edge transition-[background-color,box-shadow] duration-150 outline-none hover:bg-brand-soft hover:ring-primary/40 focus-visible:ring-2 focus-visible:ring-ring"
					>
						<span class="text-[0.9375rem] font-medium text-ink"><bdi>{pick(c, 'name')}</bdi></span>
						<ArrowRightIcon
							class="rtl-flip size-4 shrink-0 text-ink-3 transition-[color,transform] duration-200 group-hover:translate-x-0.5 group-hover:text-primary rtl:group-hover:-translate-x-0.5"
							aria-hidden="true"
						/>
					</a>
				</li>
			{/each}
		</ul>
	</section>
{/if}

<!-- ─── Promotions: administrator-set banners ──────────────────────────────── -->
{#if s.promotions?.length}
	<section class="container-page mt-10 grid gap-3 md:grid-cols-5">
		{#each s.promotions as promo, i (i)}
			<a
				href={promo.link || '/products'}
				class={cn(
					'group relative flex min-h-52 flex-col overflow-hidden rounded-2xl p-6 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:min-h-64 sm:p-8',
					promo.image_url ? 'bg-scrim text-on-scrim' : 'bg-brand-soft text-ink',
					s.promotions.length > 1 && i % 2 === 0 ? 'md:col-span-3' : 'md:col-span-2',
					s.promotions.length === 1 && 'md:col-span-5'
				)}
			>
				{#if promo.image_url}
					<img
						src={promo.image_url}
						alt=""
						class="absolute inset-0 size-full object-cover transition-transform duration-700 ease-(--ease-out) group-hover:scale-[1.03]"
					/>
					<div
						class="absolute inset-0 bg-linear-to-b from-scrim/60 via-scrim/15 to-transparent"
					></div>
				{/if}
				<div class="relative flex max-w-md flex-col gap-2">
					<p class="type-headline"><bdi>{pick(promo, 'title')}</bdi></p>
					{#if pick(promo, 'subtitle')}
						<p class="text-sm opacity-90"><bdi>{pick(promo, 'subtitle')}</bdi></p>
					{/if}
				</div>
				<span
					class="relative mt-auto inline-flex size-10 items-center justify-center self-end rounded-full bg-card text-ink shadow-soft transition-transform duration-200 group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5"
					aria-hidden="true"
				>
					<ArrowRightIcon class="rtl-flip size-4" />
				</span>
			</a>
		{/each}
	</section>
{/if}

{#if isEmpty}
	<div class="container-page mt-14">
		<EmptyState icon={StoreIcon} title={m().home.emptyTitle} description={m().home.emptyBody}>
			<Button href="/sell">{m().home.heroSecondary}</Button>
		</EmptyState>
	</div>
{/if}

{#if home.featured_products.length}
	<section class="container-page mt-14" aria-labelledby="featured-products">
		{@render sectionHead(m().home.featuredProducts, '/products', 'featured-products')}
		<div class="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-5">
			{#each home.featured_products.slice(0, 10) as product (product.id)}
				<ProductCard {product} />
			{/each}
		</div>
	</section>
{/if}

{#if home.featured_stores.length}
	<section class="container-page mt-16" aria-labelledby="featured-stores">
		{@render sectionHead(m().home.featuredStores, '/stores', 'featured-stores')}
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each home.featured_stores.slice(0, 6) as store (store.id)}
				<StoreCard {store} />
			{/each}
		</div>
	</section>
{/if}

<!-- ─── How the marketplace works: one band, three plain statements ────────── -->
<section class="mt-16 border-y border-line bg-surface-2">
	<div class="container-page grid gap-8 py-10 md:grid-cols-3 md:gap-0 md:py-12">
		{#each promises as p, i (p.title)}
			<div
				class={cn(
					'flex gap-4 md:px-8',
					i === 0 && 'md:ps-0',
					i === promises.length - 1 && 'md:pe-0',
					i > 0 && 'md:border-s md:border-line'
				)}
			>
				<p.icon class="mt-0.5 size-6 shrink-0 text-primary" aria-hidden="true" />
				<div class="flex flex-col gap-1.5">
					<h3 class="text-base font-semibold text-ink">{p.title}</h3>
					<p class="text-sm leading-relaxed text-ink-2">{p.body}</p>
				</div>
			</div>
		{/each}
	</div>
</section>

{#if home.popular_services.length}
	<section class="container-page mt-16" aria-labelledby="popular-services">
		{@render sectionHead(m().home.popularServices, '/services', 'popular-services')}
		<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
			{#each home.popular_services.slice(0, 6) as service (service.id)}
				<ServiceCard {service} />
			{/each}
		</div>
	</section>
{/if}

{#if newStores.length}
	<section class="container-page mt-16" aria-labelledby="recent-stores">
		{@render sectionHead(m().home.recentStores, '/stores?sort=newest', 'recent-stores')}
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each newStores as store (store.id)}
				<StoreCard {store} />
			{/each}
		</div>
	</section>
{/if}

{#if s.testimonials?.length}
	<section class="container-page mt-16" aria-labelledby="testimonials">
		{@render sectionHead(m().home.testimonials, undefined, 'testimonials')}
		<div class="grid gap-x-10 gap-y-8 md:grid-cols-3">
			{#each s.testimonials as t, i (i)}
				<figure class="flex flex-col gap-3 border-t-2 border-primary pt-5">
					<blockquote class="text-lg leading-relaxed text-ink">
						“<bdi>{pick(t, 'quote')}</bdi>”
					</blockquote>
					<figcaption class="text-sm text-ink-3"><bdi>{t.name}</bdi></figcaption>
				</figure>
			{/each}
		</div>
	</section>
{/if}

<!-- ─── Close: the invitation to merchants ─────────────────────────────────── -->
<section class="container-page mt-16">
	<div
		class="flex flex-col items-start justify-between gap-6 rounded-2xl bg-brand-soft p-6 sm:p-10 md:flex-row md:items-center"
	>
		<div class="flex max-w-2xl flex-col gap-2">
			<h2 class="type-headline text-ink">{m().nav.sell}</h2>
			<p class="text-pretty text-ink-2">{m().footer.about}</p>
		</div>
		<Button href="/sell" size="lg" class="shrink-0">
			<StoreIcon data-icon="inline-start" />{m().home.heroSecondary}
		</Button>
	</div>
</section>
