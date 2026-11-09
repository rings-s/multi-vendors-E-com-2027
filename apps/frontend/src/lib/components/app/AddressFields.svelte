<script lang="ts" module>
	export interface AddressValue {
		region: string;
		city: string;
		district?: string;
		street?: string;
		building_number?: string;
		postal_code?: string;
		/** Optional WGS84 delivery pin (set by "Detect my location"). */
		latitude?: number | null;
		longitude?: number | null;
	}

	/** A complete customer-address request body (every optional text field defaults to ""). */
	export function addressBody(
		a: AddressValue & {
			recipient_name: string;
			phone: string;
			label?: string;
			additional_info?: string;
			delivery_instructions?: string;
			is_default?: boolean;
		}
	) {
		return {
			label: a.label ?? '',
			recipient_name: a.recipient_name,
			phone: a.phone,
			region: a.region,
			city: a.city,
			district: a.district ?? '',
			street: a.street ?? '',
			building_number: a.building_number ?? '',
			postal_code: a.postal_code ?? '',
			additional_info: a.additional_info ?? '',
			delivery_instructions: a.delivery_instructions ?? '',
			latitude: a.latitude ?? null,
			longitude: a.longitude ?? null,
			is_default: a.is_default ?? false
		};
	}
</script>

<script lang="ts">
	import LocateFixedIcon from '@lucide/svelte/icons/locate-fixed';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import XIcon from '@lucide/svelte/icons/x';
	import { mapsLink } from '#lib/delivery.js';
	import { toast } from 'svelte-sonner';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { DetectLocationError, detectAddress } from '#lib/geo.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { m, locale } from '#lib/i18n/state.svelte.js';
	import { CITIES, REGIONS } from '#lib/saudi.js';
	import FormField from './FormField.svelte';

	interface Props {
		value: AddressValue;
		errors?: Record<string, string>;
		/** Prefix of backend field paths, e.g. "address." for nested bodies. */
		errorPrefix?: string;
		idPrefix: string;
		/** Show a "Detect my location" button that fills the fields from the device's position. */
		detectLocation?: boolean;
	}

	let {
		value = $bindable(),
		errors = {},
		errorPrefix = '',
		idPrefix,
		detectLocation = false
	}: Props = $props();
	const err = (k: string) => errors[`${errorPrefix}${k}`];
	const cities = $derived(CITIES[value.region] ?? []);

	let detecting = $state(false);

	async function detect() {
		detecting = true;
		try {
			const found = await detectAddress(locale());
			// Merge: fields the geocoder couldn't resolve keep whatever the customer typed.
			Object.assign(value, found);
			toast.success(m().account.locationDetected);
		} catch (e) {
			const code = e instanceof DetectLocationError ? e.code : 'lookup';
			toast.error(m().account.locationErrors[code]);
		} finally {
			detecting = false;
		}
	}
</script>

<Field.Group class="grid gap-4 sm:grid-cols-2">
	{#if detectLocation}
		<div class="sm:col-span-2">
			<Button
				type="button"
				variant="outline"
				size="sm"
				onclick={detect}
				disabled={detecting}
				aria-busy={detecting || undefined}
			>
				{#if detecting}<Spinner data-icon="inline-start" />{:else}<LocateFixedIcon
						data-icon="inline-start"
					/>{/if}
				{detecting ? m().account.detectingLocation : m().account.detectLocation}
			</Button>
			{#if value.latitude != null && value.longitude != null}
				<p class="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-2">
					<MapPinIcon class="size-4" aria-hidden="true" />
					<a
						href={mapsLink(value.latitude, value.longitude)}
						target="_blank"
						rel="noopener noreferrer"
						class="tabular underline underline-offset-2"
						dir="ltr">{value.latitude.toFixed(5)}, {value.longitude.toFixed(5)}</a
					>
					<Button
						type="button"
						variant="ghost"
						size="icon-sm"
						aria-label={m().merchant.clearPin}
						onclick={() => {
							value.latitude = null;
							value.longitude = null;
						}}><XIcon /></Button
					>
				</p>
			{:else}
				<p class="mt-2 text-xs text-ink-3">{m().delivery.pinHint}</p>
			{/if}
		</div>
	{/if}
	<FormField label={m().account.region} id="{idPrefix}-region" error={err('region')}>
		{#snippet children({ id, invalid })}
			<NativeSelect.Root
				{id}
				bind:value={value.region}
				aria-invalid={invalid || undefined}
				class="w-full"
				required
			>
				<NativeSelect.Option value="" disabled>{m().common.none}</NativeSelect.Option>
				{#each REGIONS as r (r.key)}
					<NativeSelect.Option value={r.key}>{r[locale()]}</NativeSelect.Option>
				{/each}
			</NativeSelect.Root>
		{/snippet}
	</FormField>
	<FormField label={m().account.city} id="{idPrefix}-city" error={err('city')}>
		{#snippet children({ id, invalid })}
			<Input
				{id}
				bind:value={value.city}
				list="{idPrefix}-cities"
				autocomplete="address-level2"
				aria-invalid={invalid || undefined}
				required
				minlength={2}
			/>
			<datalist id="{idPrefix}-cities">
				{#each cities as c (c.en)}<option value={c[locale()]}></option>{/each}
			</datalist>
		{/snippet}
	</FormField>
	<FormField label={m().account.district} id="{idPrefix}-district" error={err('district')} optional>
		{#snippet children({ id, invalid })}
			<Input {id} bind:value={value.district} aria-invalid={invalid || undefined} />
		{/snippet}
	</FormField>
	<FormField label={m().account.street} id="{idPrefix}-street" error={err('street')} optional>
		{#snippet children({ id, invalid })}
			<Input
				{id}
				bind:value={value.street}
				autocomplete="address-line1"
				aria-invalid={invalid || undefined}
			/>
		{/snippet}
	</FormField>
	<FormField
		label={m().account.buildingNumber}
		id="{idPrefix}-building"
		error={err('building_number')}
		optional
	>
		{#snippet children({ id, invalid })}
			<Input
				{id}
				bind:value={value.building_number}
				inputmode="numeric"
				aria-invalid={invalid || undefined}
			/>
		{/snippet}
	</FormField>
	<FormField
		label={m().account.postalCode}
		id="{idPrefix}-postal"
		error={err('postal_code')}
		optional
	>
		{#snippet children({ id, invalid })}
			<Input
				{id}
				bind:value={value.postal_code}
				inputmode="numeric"
				maxlength={5}
				pattern="\d{5}"
				autocomplete="postal-code"
				aria-invalid={invalid || undefined}
				dir="ltr"
			/>
		{/snippet}
	</FormField>
</Field.Group>
