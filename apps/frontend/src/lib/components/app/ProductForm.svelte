<script lang="ts">
	import { untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import { api, call } from '#lib/api/client.js';
	import type { Category, Product } from '#lib/api/types.js';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { halalasToSar, sarToHalalas } from '#lib/format.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { m, pick } from '#lib/i18n/state.svelte.js';
	import FormField from './FormField.svelte';
	import ImageUpload from './ImageUpload.svelte';

	let { product, categories }: { product?: Product | null; categories: Category[] } = $props();

	interface VariantRow {
		id?: string;
		name: string;
		sku: string;
		price: string;
		discounted: string;
		stock: string;
		options: string;
		is_active: boolean;
	}

	const form = new FormState();
	// The form is seeded once; the edit page re-mounts it (`{#key}`) when the product changes.
	const p = untrack(() => product);
	let v = $state({
		title: p?.title ?? '',
		description: p?.description ?? '',
		sku: p?.sku ?? '',
		price: halalasToSar(p?.price),
		discounted: halalasToSar(p?.discounted_price),
		category_id: p?.category_id ?? '',
		is_available: p?.is_available ?? true,
		requires_shipping: p?.requires_shipping ?? true,
		weight: p?.weight_grams != null ? String(p.weight_grams) : '',
		stock: '0'
	});
	let images = $state((p?.images ?? []).map((i) => ({ url: i.url, alt: i.alt })));
	let variants = $state<VariantRow[]>(
		(p?.variants ?? []).map((x) => ({
			id: x.id,
			name: x.name,
			sku: x.sku,
			price: halalasToSar(x.price),
			discounted: halalasToSar(x.discounted_price),
			stock: String(x.available_quantity),
			options: Object.entries(x.options ?? {})
				.map(([k, val]) => `${k}=${val}`)
				.join(', '),
			is_active: x.is_active
		}))
	);
	const cats = $derived(categories.filter((c) => c.is_active && c.kind !== 'SERVICE'));

	function parseOptions(s: string): Record<string, string> {
		const out: Record<string, string> = {};
		for (const part of s.split(/[,،]/)) {
			const [k, ...rest] = part.split('=');
			if (k?.trim() && rest.length) out[k.trim()] = rest.join('=').trim();
		}
		return out;
	}

	function money(field: string, raw: string, required: boolean): number | null | undefined {
		if (!raw.trim()) {
			if (required) form.fail(field, m().errors.invalidAmount);
			return null;
		}
		const h = sarToHalalas(raw);
		if (h == null) form.fail(field, m().errors.invalidAmount);
		return h;
	}

	async function save(status: 'DRAFT' | 'ACTIVE') {
		form.reset();
		const price = money('price', v.price, true);
		const discounted = money('discounted_price', v.discounted, false);
		const variantBodies = variants.map((row, i) => ({
			id: row.id ?? null,
			name: row.name,
			sku: row.sku,
			options: parseOptions(row.options),
			price: money(`variants.${i}.price`, row.price, false),
			discounted_price: money(`variants.${i}.discounted_price`, row.discounted, false),
			is_active: row.is_active,
			stock_quantity: Math.max(0, Math.floor(Number(row.stock) || 0))
		}));
		if (form.hasErrors) return;
		const common = {
			title: v.title,
			description: v.description,
			sku: v.sku,
			price: price!,
			discounted_price: discounted ?? null,
			category_id: v.category_id || null,
			status,
			is_available: v.is_available,
			requires_shipping: v.requires_shipping,
			weight_grams: v.weight ? Math.floor(Number(v.weight)) : null,
			images: images.map((i) => ({ url: i.url, alt: i.alt ?? '' })),
			variants: variantBodies
		};
		const res = await form.submit(
			() =>
				p
					? call(
							api.PATCH('/api/v1/merchant/products/{product_id}', {
								params: { path: { product_id: p.id } },
								body: { ...common, clear_discount: discounted == null }
							})
						)
					: call(
							api.POST('/api/v1/merchant/products', {
								body: { ...common, stock_quantity: Math.max(0, Math.floor(Number(v.stock) || 0)) }
							})
						),
			{ success: m().common.saved }
		);
		if (res.ok) await goto('/merchant/products', { invalidateAll: true });
	}

	function addVariant() {
		variants = [
			...variants,
			{
				name: '',
				sku: `${v.sku}-${variants.length + 1}`,
				price: '',
				discounted: '',
				stock: '0',
				options: '',
				is_active: true
			}
		];
	}
</script>

<form
	class="grid gap-8 xl:grid-cols-[1fr_20rem]"
	onsubmit={(e) => {
		e.preventDefault();
		save('ACTIVE');
	}}
	novalidate
>
	<div class="flex flex-col gap-6">
		{#if p?.status === 'BLOCKED'}
			<Alert.Root variant="destructive"
				><Alert.Title>{m().errors.codes.product_blocked}</Alert.Title
				>{#if p.moderation_note}<Alert.Description
						>{m().merchant.moderationNote}: {p.moderation_note}</Alert.Description
					>{/if}</Alert.Root
			>
		{/if}
		{#if form.message}<Alert.Root variant="destructive"
				><Alert.Description>{form.message}</Alert.Description></Alert.Root
			>{/if}
		<Card.Root>
			<Card.Content>
				<Field.Group>
					<FormField label={m().merchant.productTitle} id="pr-title" error={form.errors.title}>
						{#snippet children({ id, invalid })}<Input
								{id}
								bind:value={v.title}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField
						label={m().catalog.description}
						id="pr-desc"
						error={form.errors.description}
						optional
					>
						{#snippet children({ id })}<Textarea
								{id}
								rows={6}
								bind:value={v.description}
							/>{/snippet}
					</FormField>
					<ImageUpload bind:images purpose="product" label={m().merchant.images} id="pr-images" />
				</Field.Group>
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Content>
				<Field.Group class="grid gap-4 sm:grid-cols-2">
					<FormField label={m().merchant.price} id="pr-price" error={form.errors.price}>
						{#snippet children({ id, invalid })}<Input
								{id}
								inputmode="decimal"
								dir="ltr"
								bind:value={v.price}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField
						label={m().merchant.discountedPrice}
						id="pr-disc"
						error={form.errors.discounted_price}
						optional
					>
						{#snippet children({ id, invalid })}<Input
								{id}
								inputmode="decimal"
								dir="ltr"
								bind:value={v.discounted}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField label={m().catalog.sku} id="pr-sku" error={form.errors.sku}>
						{#snippet children({ id, invalid })}<Input
								{id}
								dir="ltr"
								bind:value={v.sku}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					{#if !p}
						<FormField
							label={m().merchant.stockQuantity}
							id="pr-stock"
							error={form.errors.stock_quantity}
						>
							{#snippet children({ id })}<Input
									{id}
									type="number"
									min={0}
									bind:value={v.stock}
								/>{/snippet}
						</FormField>
					{/if}
					<FormField
						label={m().merchant.weight}
						id="pr-weight"
						error={form.errors.weight_grams}
						optional
					>
						{#snippet children({ id })}<Input
								{id}
								type="number"
								min={0}
								bind:value={v.weight}
							/>{/snippet}
					</FormField>
				</Field.Group>
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Header>
				<Card.Title role="heading" aria-level={2}>{m().merchant.variants}</Card.Title>
				<Card.Action>
					<Button type="button" variant="outline" size="sm" onclick={addVariant}
						><PlusIcon data-icon="inline-start" />{m().merchant.addVariant}</Button
					>
				</Card.Action>
			</Card.Header>
			{#if variants.length}
				<Card.Content class="flex flex-col gap-4">
					{#each variants as row, i (i)}
						<Field.Set class="rounded-xl border border-line p-4">
							<Field.Legend class="sr-only">{m().catalog.variant} {i + 1}</Field.Legend>
							<Field.Group class="grid gap-3 sm:grid-cols-6">
								<FormField
									label={m().merchant.variantName}
									id="v{i}-name"
									error={form.errors[`variants.${i}.name`]}
									class="sm:col-span-2"
								>
									{#snippet children({ id })}<Input {id} bind:value={row.name} />{/snippet}
								</FormField>
								<FormField
									label={m().catalog.sku}
									id="v{i}-sku"
									error={form.errors[`variants.${i}.sku`]}
									class="sm:col-span-2"
								>
									{#snippet children({ id })}<Input {id} dir="ltr" bind:value={row.sku} />{/snippet}
								</FormField>
								<FormField label={m().merchant.stockQuantity} id="v{i}-stock" class="sm:col-span-2">
									{#snippet children({ id })}<Input
											{id}
											type="number"
											min={0}
											bind:value={row.stock}
											disabled={!!row.id}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().merchant.price}
									id="v{i}-price"
									error={form.errors[`variants.${i}.price`]}
									class="sm:col-span-2"
									optional
								>
									{#snippet children({ id })}<Input
											{id}
											inputmode="decimal"
											dir="ltr"
											bind:value={row.price}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().merchant.variantOptions}
									id="v{i}-opts"
									hint={m().merchant.variantOptionsHint}
									class="sm:col-span-3"
									optional
								>
									{#snippet children({ id, describedBy })}<Input
											{id}
											dir="ltr"
											bind:value={row.options}
											aria-describedby={describedBy}
										/>{/snippet}
								</FormField>
								<div
									class="flex items-end justify-between gap-2 sm:col-span-1 sm:flex-col sm:items-end"
								>
									<Field.Field orientation="horizontal" class="w-auto">
										<Checkbox id="v{i}-active" bind:checked={row.is_active} /><Field.Label
											for="v{i}-active"
											class="font-normal">{m().merchant.variantActive}</Field.Label
										>
									</Field.Field>
									{#if !row.id}<Button
											type="button"
											size="icon-sm"
											variant="ghost"
											aria-label={m().common.remove}
											onclick={() => (variants = variants.filter((_, j) => j !== i))}
											><Trash2Icon /></Button
										>{/if}
								</div>
							</Field.Group>
						</Field.Set>
					{/each}
				</Card.Content>
			{/if}
		</Card.Root>
	</div>

	<Card.Root class="h-fit xl:sticky xl:top-24">
		<Card.Content>
			<Field.Group>
				<FormField label={m().stores.category} id="pr-cat" error={form.errors.category_id}>
					{#snippet children({ id })}
						<NativeSelect.Root {id} bind:value={v.category_id} class="w-full">
							<NativeSelect.Option value="">{m().common.none}</NativeSelect.Option>
							{#each cats as c (c.id)}<NativeSelect.Option value={c.id}
									>{pick(c, 'name')}</NativeSelect.Option
								>{/each}
						</NativeSelect.Root>
					{/snippet}
				</FormField>
				<Field.Field orientation="horizontal">
					<Field.Label for="pr-avail" class="font-normal">{m().merchant.isAvailable}</Field.Label
					><Switch id="pr-avail" bind:checked={v.is_available} />
				</Field.Field>
				<Field.Field orientation="horizontal">
					<Field.Label for="pr-ship" class="font-normal"
						>{m().merchant.requiresShipping}</Field.Label
					><Switch id="pr-ship" bind:checked={v.requires_shipping} />
				</Field.Field>
			</Field.Group>
		</Card.Content>
		<Card.Footer class="flex-col items-stretch gap-2">
			<Button type="submit" disabled={form.pending} data-testid="publish-product"
				>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().merchant
					.statusActive}</Button
			>
			<Button type="button" variant="outline" disabled={form.pending} onclick={() => save('DRAFT')}
				>{m().merchant.statusDraft}</Button
			>
		</Card.Footer>
	</Card.Root>
</form>
