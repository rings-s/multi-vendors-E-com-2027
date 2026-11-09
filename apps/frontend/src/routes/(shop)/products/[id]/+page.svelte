<script lang="ts">
	import TruckIcon from '@lucide/svelte/icons/truck';
	import AddToCart from '#lib/components/app/AddToCart.svelte';
	import CardGridSkeleton from '#lib/components/app/CardGridSkeleton.svelte';
	import Gallery from '#lib/components/app/Gallery.svelte';
	import StoreLinkItem from '#lib/components/app/StoreLinkItem.svelte';
	import PriceTag from '#lib/components/app/PriceTag.svelte';
	import ProductCard from '#lib/components/app/ProductCard.svelte';
	import QuantityStepper from '#lib/components/app/QuantityStepper.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Breadcrumb from '#lib/components/ui/breadcrumb/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as ToggleGroup from '#lib/components/ui/toggle-group/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const p = $derived(data.product);
	const variants = $derived(p.variants.filter((v) => v.is_active));
	let variantId = $state<string | null>(null);
	let quantity = $state(1);

	$effect(() => {
		// Reset the selection when navigating between products.
		void p.id;
		variantId = variants.length === 1 ? variants[0].id : null;
		quantity = 1;
	});

	const variant = $derived(variants.find((v) => v.id === variantId) ?? null);
	const price = $derived(variant ? variant.price : p.price);
	const discounted = $derived(variant ? variant.discounted_price : p.discounted_price);
	const available = $derived(variant ? variant.available_quantity : p.available_quantity);
	const needsVariant = $derived(variants.length > 0 && !variant);
	const canBuy = $derived(p.is_available && available > 0 && !needsVariant);
</script>

<svelte:head>
	<title>{p.title} · {p.store.name}</title>
	<meta name="description" content={p.description.slice(0, 160)} />
</svelte:head>

<div class="container-page py-8">
	<Breadcrumb.Root class="mb-6">
		<Breadcrumb.List>
			<Breadcrumb.Item
				><Breadcrumb.Link href="/products">{m().nav.products}</Breadcrumb.Link></Breadcrumb.Item
			>
			<Breadcrumb.Separator />
			<Breadcrumb.Item
				><Breadcrumb.Link href="/stores/{p.store.slug}"><bdi>{p.store.name}</bdi></Breadcrumb.Link
				></Breadcrumb.Item
			>
			<Breadcrumb.Separator />
			<Breadcrumb.Item
				><Breadcrumb.Page class="line-clamp-1"><bdi>{p.title}</bdi></Breadcrumb.Page
				></Breadcrumb.Item
			>
		</Breadcrumb.List>
	</Breadcrumb.Root>

	<div class="grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-16">
		<Gallery images={p.images} title={p.title} />

		<div class="flex flex-col gap-8 lg:sticky lg:top-24 lg:self-start">
			<div class="flex flex-col gap-4">
				<a
					href="/stores/{p.store.slug}"
					class="self-start text-sm tracking-wide text-ink-3 hover:text-ink"
					><bdi>{p.store.name}</bdi></a
				>
				<h1 class="font-display text-3xl leading-tight text-ink sm:text-4xl">
					<bdi>{p.title}</bdi>
				</h1>
				<PriceTag {price} {discounted} size="lg" />
				<p class="text-sm" data-testid="stock">
					{#if !p.is_available}
						<span class="text-ink-3">{m().catalog.unavailable}</span>
					{:else if available <= 0}
						<span class="text-danger">{m().catalog.outOfStock}</span>
					{:else if available <= 5}
						<span class="text-warning">{m().catalog.onlyLeft({ n: available })}</span>
					{:else}
						<span class="text-success">{m().catalog.inStock}</span>
					{/if}
				</p>
			</div>

			{#if variants.length}
				<Field.Set>
					<Field.Legend variant="label">{m().catalog.variant}</Field.Legend>
					<ToggleGroup.Root
						type="single"
						variant="outline"
						size="lg"
						spacing={2}
						class="flex-wrap"
						aria-label={m().catalog.variant}
						bind:value={() => variantId ?? '', (v) => v && (variantId = v)}
					>
						{#each variants as v (v.id)}
							<ToggleGroup.Item
								value={v.id}
								disabled={v.available_quantity <= 0}
								class="px-4 data-[state=on]:border-primary"
							>
								<bdi>{v.name}</bdi>
							</ToggleGroup.Item>
						{/each}
					</ToggleGroup.Root>
					{#if needsVariant}<Field.Description>{m().catalog.chooseVariant}</Field.Description>{/if}
				</Field.Set>
			{/if}

			<div class="flex items-center gap-4">
				<span class="text-sm text-ink-2">{m().catalog.quantity}</span>
				<QuantityStepper
					bind:value={quantity}
					max={Math.max(1, Math.min(available, 999))}
					disabled={!canBuy}
				/>
			</div>

			<AddToCart item={{ product_id: p.id, variant_id: variantId, quantity }} disabled={!canBuy} />

			<Alert.Root role="note">
				<TruckIcon aria-hidden="true" />
				<Alert.Description>
					{p.requires_shipping ? m().catalog.requiresShipping : m().catalog.noShipping}
				</Alert.Description>
			</Alert.Root>

			<Separator />

			<section class="flex flex-col gap-3">
				<h2 class="font-medium text-ink">{m().catalog.description}</h2>
				<div class="leading-relaxed whitespace-pre-line text-ink-2">
					<bdi>{p.description || '—'}</bdi>
				</div>
				<p class="text-xs text-ink-3">
					{m().catalog.sku}: <span dir="ltr" class="tabular">{variant?.sku ?? p.sku}</span>
				</p>
			</section>

			<StoreLinkItem store={p.store} />
			<p class="text-xs text-ink-3">{m().catalog.vatNote}</p>
		</div>
	</div>

	{#await data.more}
		<div class="mt-20"><CardGridSkeleton count={4} /></div>
	{:then more}
		{#if more.length}
			<section class="mt-20 flex flex-col gap-6">
				<h2 class="type-title">{m().catalog.soldBy} <bdi>{p.store.name}</bdi></h2>
				<div class="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-4">
					{#each more as product (product.id)}<ProductCard {product} showStore={false} />{/each}
				</div>
			</section>
		{/if}
	{:catch}
		<!-- Related products are optional. -->
	{/await}
</div>
