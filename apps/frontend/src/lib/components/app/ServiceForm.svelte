<script lang="ts">
	import { untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, call } from '#lib/api/client.js';
	import type { Category, Service } from '#lib/api/types.js';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
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

	let { service, categories }: { service?: Service | null; categories: Category[] } = $props();
	// Seeded once; the edit page re-mounts the form per service.
	const s = untrack(() => service);
	const form = new FormState();
	type LocationType = 'AT_STORE' | 'AT_CUSTOMER' | 'ONLINE';
	let v = $state({
		title: s?.title ?? '',
		description: s?.description ?? '',
		price: halalasToSar(s?.price),
		discounted: halalasToSar(s?.discounted_price),
		duration: s?.duration_minutes != null ? String(s.duration_minutes) : '60',
		category_id: s?.category_id ?? '',
		available: (s?.availability ?? 'AVAILABLE') === 'AVAILABLE',
		location_type: (s?.location_type ?? 'AT_STORE') as LocationType,
		location: s?.location ?? ''
	});
	let images = $state((s?.images ?? []).map((i) => ({ url: i.url, alt: i.alt })));
	const cats = $derived(categories.filter((c) => c.is_active && c.kind !== 'PRODUCT'));

	async function save(status: 'DRAFT' | 'ACTIVE') {
		form.reset();
		const price = sarToHalalas(v.price);
		const discounted = v.discounted.trim() ? sarToHalalas(v.discounted) : null;
		const duration = Math.floor(Number(v.duration));
		if (price == null) form.fail('price', m().errors.invalidAmount);
		if (v.discounted.trim() && discounted == null)
			form.fail('discounted_price', m().errors.invalidAmount);
		if (!(duration > 0)) form.fail('duration_minutes', m().common.required);
		if (form.hasErrors) return;
		const body = {
			title: v.title,
			description: v.description,
			price: price!,
			discounted_price: discounted,
			duration_minutes: duration,
			category_id: v.category_id || null,
			availability: (v.available ? 'AVAILABLE' : 'UNAVAILABLE') as 'AVAILABLE' | 'UNAVAILABLE',
			location_type: v.location_type,
			location: v.location,
			status,
			images: images.map((i) => ({ url: i.url, alt: i.alt ?? '' }))
		};
		const res = await form.submit(
			() =>
				s
					? call(
							api.PATCH('/api/v1/merchant/services/{service_id}', {
								params: { path: { service_id: s.id } },
								body: { ...body, clear_discount: discounted == null }
							})
						)
					: call(api.POST('/api/v1/merchant/services', { body })),
			{ success: m().common.saved }
		);
		if (res.ok) await goto('/merchant/services', { invalidateAll: true });
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
		{#if s?.status === 'BLOCKED'}
			<Alert.Root variant="destructive"
				><Alert.Title>{m().errors.codes.service_blocked}</Alert.Title
				>{#if s.moderation_note}<Alert.Description
						>{m().merchant.moderationNote}: {s.moderation_note}</Alert.Description
					>{/if}</Alert.Root
			>
		{/if}
		{#if form.message}<Alert.Root variant="destructive"
				><Alert.Description>{form.message}</Alert.Description></Alert.Root
			>{/if}
		<Card.Root>
			<Card.Content>
				<Field.Group>
					<FormField label={m().merchant.productTitle} id="sv-title" error={form.errors.title}>
						{#snippet children({ id, invalid })}<Input
								{id}
								bind:value={v.title}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField label={m().catalog.description} id="sv-desc" optional>
						{#snippet children({ id })}<Textarea
								{id}
								rows={6}
								bind:value={v.description}
							/>{/snippet}
					</FormField>
					<ImageUpload bind:images purpose="service" label={m().merchant.images} id="sv-images" />
				</Field.Group>
			</Card.Content>
		</Card.Root>
		<Card.Root>
			<Card.Content>
				<Field.Group class="grid gap-4 sm:grid-cols-2">
					<FormField label={m().merchant.price} id="sv-price" error={form.errors.price}>
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
						id="sv-disc"
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
					<FormField
						label={m().merchant.durationMinutes}
						id="sv-dur"
						error={form.errors.duration_minutes}
					>
						{#snippet children({ id, invalid })}<Input
								{id}
								type="number"
								min={1}
								max={43200}
								bind:value={v.duration}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField label={m().merchant.locationType} id="sv-lt">
						{#snippet children({ id })}
							<NativeSelect.Root {id} bind:value={v.location_type} class="w-full">
								<NativeSelect.Option value="AT_STORE"
									>{m().catalog.locationAtStore}</NativeSelect.Option
								>
								<NativeSelect.Option value="AT_CUSTOMER"
									>{m().catalog.locationAtCustomer}</NativeSelect.Option
								>
								<NativeSelect.Option value="ONLINE"
									>{m().catalog.locationOnline}</NativeSelect.Option
								>
							</NativeSelect.Root>
						{/snippet}
					</FormField>
					<FormField
						label={m().merchant.locationDetails}
						id="sv-loc"
						optional
						class="sm:col-span-2"
					>
						{#snippet children({ id })}<Input
								{id}
								bind:value={v.location}
								maxlength={300}
							/>{/snippet}
					</FormField>
				</Field.Group>
			</Card.Content>
		</Card.Root>
	</div>
	<Card.Root class="h-fit xl:sticky xl:top-24">
		<Card.Content>
			<Field.Group>
				<FormField label={m().stores.category} id="sv-cat">
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
					<Field.Label for="sv-avail" class="font-normal">{m().merchant.availability}</Field.Label
					><Switch id="sv-avail" bind:checked={v.available} />
				</Field.Field>
			</Field.Group>
		</Card.Content>
		<Card.Footer class="flex-col items-stretch gap-2">
			<Button type="submit" disabled={form.pending}
				>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().merchant
					.statusActive}</Button
			>
			<Button type="button" variant="outline" disabled={form.pending} onclick={() => save('DRAFT')}
				>{m().merchant.statusDraft}</Button
			>
		</Card.Footer>
	</Card.Root>
</form>
