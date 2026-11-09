<script lang="ts">
	import { invalidate } from '$app/navigation';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import { api, call } from '#lib/api/client.js';
	import type { Location } from '#lib/api/types.js';
	import AddressFields from '#lib/components/app/AddressFields.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import ImageUpload from '#lib/components/app/ImageUpload.svelte';
	import LocationMap, { type MapPin } from '#lib/components/app/LocationMap.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { normalizeSaudiMobile } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m, pick } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const form = new FormState();
	let v = $state({
		name: '',
		description: '',
		region: '',
		city: '',
		contact_email: '',
		contact_phone: '',
		is_open: true,
		return_policy: '',
		category_ids: [] as string[]
	});
	let logo = $state<{ url: string }[]>([]);
	let cover = $state<{ url: string }[]>([]);

	$effect.pre(() => {
		const s = data.store;
		v = {
			name: s.name,
			description: s.description,
			region: s.region,
			city: s.city,
			contact_email: s.contact_email ?? '',
			contact_phone: s.contact_phone ?? '',
			is_open: s.is_open,
			return_policy: s.return_policy,
			category_ids: [...(s.category_ids ?? [])]
		};
		logo = s.logo_url ? [{ url: s.logo_url }] : [];
		cover = s.cover_url ? [{ url: s.cover_url }] : [];
	});

	async function save(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const phone = v.contact_phone.trim() ? normalizeSaudiMobile(v.contact_phone) : null;
		if (v.contact_phone.trim() && !phone) form.fail('contact_phone', m().errors.invalidPhone);
		if (form.hasErrors) return;
		const res = await form.submit(
			() =>
				call(
					api.PATCH('/api/v1/merchant/store', {
						body: {
							...v,
							contact_email: v.contact_email || null,
							contact_phone: phone,
							logo_url: logo[0]?.url ?? '',
							cover_url: cover[0]?.url ?? ''
						}
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) await invalidate('app:store');
	}

	function toggleCategory(id: string, on: boolean) {
		v.category_ids = on
			? [...new Set([...v.category_ids, id])]
			: v.category_ids.filter((x) => x !== id);
	}

	// Locations
	const locForm = new FormState();
	let locOpen = $state(false);
	let locEditing = $state<Location | null>(null);
	let loc = $state({
		label: '',
		region: '',
		city: '',
		district: '',
		street: '',
		building_number: '',
		postal_code: '',
		is_pickup_location: false,
		latitude: null as number | null,
		longitude: null as number | null
	});

	function editLocation(l: Location | null) {
		locEditing = l;
		loc = l
			? {
					label: l.label ?? '',
					region: l.region,
					city: l.city,
					district: l.district ?? '',
					street: l.street ?? '',
					building_number: l.building_number ?? '',
					postal_code: l.postal_code ?? '',
					is_pickup_location: !!l.is_pickup_location,
					latitude: l.latitude ?? null,
					longitude: l.longitude ?? null
				}
			: {
					label: '',
					region: '',
					city: '',
					district: '',
					street: '',
					building_number: '',
					postal_code: '',
					is_pickup_location: false,
					latitude: null,
					longitude: null
				};
		locForm.reset();
		locOpen = true;
	}

	const pins = $derived<MapPin[]>(
		data.locations.flatMap((l) =>
			l.latitude != null && l.longitude != null
				? [{ id: l.id, lat: l.latitude, lng: l.longitude, label: l.label || l.city }]
				: []
		)
	);

	async function saveLocation(e: SubmitEvent) {
		e.preventDefault();
		const res = await locForm.submit(
			() =>
				locEditing
					? call(
							api.PUT('/api/v1/merchant/store/locations/{location_id}', {
								params: { path: { location_id: locEditing.id } },
								body: loc
							})
						)
					: call(api.POST('/api/v1/merchant/store/locations', { body: loc })),
			{ success: m().common.saved }
		);
		if (res.ok) {
			locOpen = false;
			await invalidate('app:store');
		}
	}

	async function removeLocation(l: Location) {
		if (
			!(await confirm({
				title: `${m().common.delete}: ${l.label || l.city}?`,
				destructive: true,
				confirmLabel: m().common.delete
			}))
		)
			return;
		await action(() =>
			call(
				api.DELETE('/api/v1/merchant/store/locations/{location_id}', {
					params: { path: { location_id: l.id } }
				})
			)
		);
		await invalidate('app:store');
	}
</script>

<svelte:head><title>{m().merchant.storeTitle} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={m().merchant.storeTitle}>
		{#snippet actions()}<Button href="/stores/{data.store.slug}" variant="outline" target="_blank"
				>{m().merchant.viewStorefront}</Button
			>{/snippet}
	</PageHeader>

	<form class="flex flex-col gap-8" onsubmit={save} novalidate>
		<section>
			<Card.Root class="h-full">
				<Card.Content>
					<Field.Group>
						<Field.Field orientation="horizontal">
							<Field.Label for="st-open" class="font-normal">{m().merchant.isOpen}</Field.Label>
							<Switch id="st-open" bind:checked={v.is_open} />
						</Field.Field>
						<div class="grid gap-6 sm:grid-cols-[10rem_1fr]">
							<ImageUpload
								bind:images={logo}
								purpose="store"
								max={1}
								label={m().merchant.logo}
								id="st-logo"
								class="[&_ul]:grid-cols-1"
							/>
							<ImageUpload
								bind:images={cover}
								purpose="store"
								max={1}
								label={m().merchant.cover}
								id="st-cover"
								aspect="aspect-[16/9]"
								class="[&_ul]:grid-cols-1 sm:[&_ul]:grid-cols-2"
							/>
						</div>
						<div class="grid gap-4 sm:grid-cols-2">
							<FormField label={m().merchant.storeName} id="st-name" error={form.errors.name}>
								{#snippet children({ id, invalid })}<Input
										{id}
										bind:value={v.name}
										aria-invalid={invalid || undefined}
									/>{/snippet}
							</FormField>
							<FormField label={m().account.city} id="st-city" error={form.errors.city}>
								{#snippet children({ id, invalid })}<Input
										{id}
										bind:value={v.city}
										aria-invalid={invalid || undefined}
									/>{/snippet}
							</FormField>
							<FormField
								label={m().merchant.contactEmail}
								id="st-email"
								error={form.errors.contact_email}
								optional
							>
								{#snippet children({ id, invalid })}<Input
										{id}
										type="email"
										dir="ltr"
										bind:value={v.contact_email}
										aria-invalid={invalid || undefined}
									/>{/snippet}
							</FormField>
							<FormField
								label={m().merchant.contactPhone}
								id="st-phone"
								error={form.errors.contact_phone}
								optional
							>
								{#snippet children({ id, invalid })}<Input
										{id}
										type="tel"
										dir="ltr"
										bind:value={v.contact_phone}
										aria-invalid={invalid || undefined}
									/>{/snippet}
							</FormField>
							<FormField
								label={m().merchant.storeDescription}
								id="st-desc"
								error={form.errors.description}
								class="sm:col-span-2"
							>
								{#snippet children({ id })}<Textarea
										{id}
										rows={4}
										bind:value={v.description}
									/>{/snippet}
							</FormField>
						</div>
					</Field.Group>
				</Card.Content>
			</Card.Root>
		</section>

		<section>
			<Card.Root class="h-full">
				<Card.Header>
					<Card.Title role="heading" aria-level={2}>{m().stores.policies}</Card.Title>
					<Card.Description>
						<a href="/merchant/delivery" class="underline underline-offset-2"
							>{m().delivery.settingsTitle}</a
						>: {m().delivery.settingsSubtitle}
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<Field.Group>
						<div class="grid gap-4 sm:grid-cols-2">
							<FormField label={m().stores.returnPolicy} id="st-rp" class="sm:col-span-2">
								{#snippet children({ id })}<Textarea
										{id}
										rows={3}
										bind:value={v.return_policy}
									/>{/snippet}
							</FormField>
						</div>
					</Field.Group>
				</Card.Content>
			</Card.Root>
		</section>

		<Card.Root>
			<Card.Content>
				<Field.Set>
					<Field.Legend>{m().merchant.storeCategories}</Field.Legend>
					<Field.Group class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
						{#each data.categories.filter((c) => c.is_active) as c (c.id)}
							<Field.Field orientation="horizontal">
								<Checkbox
									id="cat-{c.id}"
									checked={v.category_ids.includes(c.id)}
									onCheckedChange={(on) => toggleCategory(c.id, !!on)}
								/>
								<Field.Label for="cat-{c.id}" class="font-normal"
									><bdi>{pick(c, 'name')}</bdi></Field.Label
								>
							</Field.Field>
						{/each}
					</Field.Group>
				</Field.Set>
			</Card.Content>
		</Card.Root>

		<div class="sticky bottom-4 z-10 flex justify-end">
			<Button type="submit" size="lg" disabled={form.pending} class="shadow-lift"
				>{#if form.pending}<Spinner data-icon="inline-start" />{m().common.saving}{:else}{m().common
						.save}{/if}</Button
			>
		</div>
	</form>

	<section class="flex flex-col gap-4">
		<div class="flex items-center justify-between">
			<h2 id="locations" class="scroll-mt-24 type-title">{m().merchant.locations}</h2>
			<Button variant="outline" onclick={() => editLocation(null)}
				><PlusIcon data-icon="inline-start" />{m().merchant.addLocation}</Button
			>
		</div>
		{#if pins.length}
			<LocationMap
				label={m().merchant.locationsMap}
				{pins}
				onselect={(id) => {
					const l = data.locations.find((x) => x.id === id);
					if (l) editLocation(l);
				}}
			/>
		{/if}
		<ul class="grid gap-4 md:grid-cols-2">
			{#each data.locations as l (l.id)}
				<li>
					<Card.Root size="sm" class="h-full">
						<Card.Header>
							<Card.Title class="flex flex-wrap items-center gap-1.5">
								<MapPinIcon class="size-4 text-ink-3" aria-hidden="true" />
								{l.label || l.city}
								{#if l.is_primary}<Badge variant="brand">{m().merchant.primary}</Badge>{/if}
								{#if l.is_pickup_location}<Badge variant="secondary">{m().merchant.pickup}</Badge
									>{/if}
							</Card.Title>
							<Card.Description>
								{fmt.list([
									l.street,
									l.building_number,
									l.district,
									l.city,
									fmt.region(l.region),
									l.postal_code
								])}
								{#if l.latitude == null}
									<span class="mt-1 block type-label text-ink-3">{m().merchant.notPinned}</span>
								{/if}
							</Card.Description>
							<Card.Action class="flex gap-1">
								<Button
									size="icon-sm"
									variant="ghost"
									aria-label={m().common.edit}
									onclick={() => editLocation(l)}><PencilIcon /></Button
								>
								{#if !l.is_primary}<Button
										size="icon-sm"
										variant="destructive"
										aria-label={m().common.delete}
										onclick={() => removeLocation(l)}><Trash2Icon /></Button
									>{/if}
							</Card.Action>
						</Card.Header>
					</Card.Root>
				</li>
			{/each}
		</ul>
	</section>
</div>

<Dialog.Root bind:open={locOpen}>
	<Dialog.Content class="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
		<form class="grid gap-4" onsubmit={saveLocation} novalidate>
			<Dialog.Header
				><Dialog.Title>{locEditing ? m().common.edit : m().merchant.addLocation}</Dialog.Title
				></Dialog.Header
			>
			<Field.Group>
				<FormField label={m().account.addressLabel} id="l-label" optional>
					{#snippet children({ id })}<Input {id} bind:value={loc.label} />{/snippet}
				</FormField>
				<AddressFields bind:value={loc} errors={locForm.errors} idPrefix="l" />
				<Field.Set>
					<Field.Legend variant="label">{m().merchant.pinOnMap}</Field.Legend>
					<LocationMap
						editable
						label={m().merchant.pinOnMap}
						bind:value={
							() =>
								loc.latitude != null && loc.longitude != null
									? { lat: loc.latitude, lng: loc.longitude }
									: null,
							(v) => {
								loc.latitude = v?.lat ?? null;
								loc.longitude = v?.lng ?? null;
							}
						}
					/>
				</Field.Set>
				<Field.Field orientation="horizontal">
					<Checkbox id="l-pickup" bind:checked={loc.is_pickup_location} /><Field.Label
						for="l-pickup"
						class="font-normal">{m().merchant.pickup}</Field.Label
					>
				</Field.Field>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (locOpen = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={locForm.pending}
					>{#if locForm.pending}<Spinner data-icon="inline-start" />{/if}{m().common.save}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
