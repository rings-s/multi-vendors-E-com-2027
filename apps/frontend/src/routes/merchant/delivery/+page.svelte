<script lang="ts">
	import { invalidate } from '$app/navigation';
	import MapPinnedIcon from '@lucide/svelte/icons/map-pinned';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import { api, call } from '#lib/api/client.js';
	import type { DeliveryZone, DeliveryZoneIn } from '#lib/api/types.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { etaRange, splitPlaces } from '#lib/delivery.js';
	import { halalasToSar, sarToHalalas } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, locale, m } from '#lib/i18n/state.svelte.js';
	import { REGIONS } from '#lib/saudi.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const settings = $derived(data.settings);
	const refresh = () => invalidate('app:delivery');

	// -- methods ------------------------------------------------------------------------
	const settingsForm = new FormState();
	let s = $state({
		delivery_enabled: true,
		pickup_enabled: false,
		pickup_preparation_minutes: '120',
		delivery_policy: ''
	});
	$effect.pre(() => {
		settingsForm.reset(); // fresh server data: drop stale field errors
		s = {
			delivery_enabled: data.settings.delivery_enabled,
			pickup_enabled: data.settings.pickup_enabled,
			pickup_preparation_minutes: String(data.settings.pickup_preparation_minutes),
			delivery_policy: data.settings.delivery_policy
		};
	});

	async function saveSettings(e: SubmitEvent) {
		e.preventDefault();
		settingsForm.reset();
		const minutes = Math.round(Number(s.pickup_preparation_minutes));
		if (!(minutes >= 0 && minutes <= 43200))
			return settingsForm.fail('pickup_preparation_minutes', m().errors.invalidAmount);
		const res = await settingsForm.submit(
			() =>
				call(
					api.PUT('/api/v1/merchant/delivery/settings', {
						body: {
							delivery_enabled: s.delivery_enabled,
							pickup_enabled: s.pickup_enabled,
							pickup_preparation_minutes: minutes,
							delivery_policy: s.delivery_policy
						}
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) await refresh();
	}

	// -- zones --------------------------------------------------------------------------
	type ZoneDraft = {
		name: string;
		region: string;
		cities: string;
		districts: string;
		fee: string;
		threshold: string;
		etaMin: string;
		etaMax: string;
		active: boolean;
	};
	const blank = (): ZoneDraft => ({
		name: '',
		region: '',
		cities: '',
		districts: '',
		fee: '',
		threshold: '',
		etaMin: '2',
		etaMax: '24',
		active: true
	});
	const hours = (minutes: number) => String(Math.round((minutes / 60) * 10) / 10);

	let open = $state(false);
	let editing = $state<DeliveryZone | null>(null);
	let z = $state<ZoneDraft>(blank());
	const zoneForm = new FormState();

	function edit(zone: DeliveryZone | null) {
		editing = zone;
		z = zone
			? {
					name: zone.name,
					region: zone.region ?? '',
					cities: (zone.cities ?? []).join(', '),
					districts: (zone.districts ?? []).join(', '),
					fee: halalasToSar(zone.fee),
					threshold: halalasToSar(zone.free_delivery_threshold),
					etaMin: hours(zone.eta_min_minutes),
					etaMax: hours(zone.eta_max_minutes),
					active: zone.is_active
				}
			: blank();
		zoneForm.reset();
		open = true;
	}

	async function saveZone(e: SubmitEvent) {
		e.preventDefault();
		zoneForm.reset();
		const fee = sarToHalalas(z.fee || '0');
		const threshold = z.threshold.trim() ? sarToHalalas(z.threshold) : null;
		const etaMin = Math.round(Number(z.etaMin) * 60);
		const etaMax = Math.round(Number(z.etaMax) * 60);
		const cities = splitPlaces(z.cities);
		const districts = splitPlaces(z.districts);
		if (z.name.trim().length < 2) zoneForm.fail('name', m().common.required);
		if (fee == null) zoneForm.fail('fee', m().errors.invalidAmount);
		if (z.threshold.trim() && threshold == null)
			zoneForm.fail('free_delivery_threshold', m().errors.invalidAmount);
		if (!(etaMin >= 0)) zoneForm.fail('eta_min_minutes', m().errors.invalidAmount);
		if (!(etaMax >= etaMin)) zoneForm.fail('eta_max_minutes', m().errors.invalidAmount);
		if (cities.length && !z.region) zoneForm.fail('region', m().common.required);
		if (districts.length && !cities.length) zoneForm.fail('cities', m().common.required);
		if (zoneForm.hasErrors) return;
		const body: DeliveryZoneIn = {
			name: z.name.trim(),
			region: z.region || null,
			cities: z.region ? cities : [],
			districts: z.region ? districts : [],
			fee: fee!,
			free_delivery_threshold: threshold,
			eta_min_minutes: etaMin,
			eta_max_minutes: etaMax,
			is_active: z.active
		};
		const zone = editing;
		const res = await zoneForm.submit(
			() =>
				zone
					? call(
							api.PUT('/api/v1/merchant/delivery/zones/{zone_id}', {
								params: { path: { zone_id: zone.id } },
								body
							})
						)
					: call(api.POST('/api/v1/merchant/delivery/zones', { body })),
			{ success: m().delivery.zoneSaved }
		);
		if (res.ok) {
			open = false;
			await refresh();
		}
	}

	async function remove(zone: DeliveryZone) {
		if (
			!(await confirm({
				title: m().delivery.deleteZone,
				description: m().delivery.deleteZoneConfirm,
				destructive: true,
				confirmLabel: m().common.delete
			}))
		)
			return;
		await action(
			() =>
				call(
					api.DELETE('/api/v1/merchant/delivery/zones/{zone_id}', {
						params: { path: { zone_id: zone.id } }
					})
				),
			m().delivery.zoneDeleted
		);
		await refresh();
	}

	const coverage = (zone: DeliveryZone) => {
		if (!zone.region) return m().delivery.allSaudi;
		const parts = [fmt.region(zone.region)];
		if (zone.cities?.length) parts.push(fmt.list(zone.cities ?? []));
		if (zone.districts?.length) parts.push(fmt.list(zone.districts ?? []));
		return parts.join(' · ');
	};
</script>

<svelte:head><title>{m().delivery.settingsTitle} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={m().delivery.settingsTitle} description={m().delivery.settingsSubtitle} />

	<div class="grid gap-6 lg:grid-cols-[1fr_22rem]">
		<Card.Root>
			<form onsubmit={saveSettings} novalidate class="contents">
				<Card.Content>
					<Field.Group>
						<Field.Field orientation="horizontal">
							<Switch id="ds-delivery" bind:checked={s.delivery_enabled} />
							<Field.Content>
								<Field.Label for="ds-delivery">{m().delivery.offerDelivery}</Field.Label>
								<Field.Description>{m().delivery.offerDeliveryHint}</Field.Description>
								{#if s.delivery_enabled && settings.active_zones === 0}
									<Field.Description class="text-warning"
										>{m().delivery.noActiveZones}</Field.Description
									>
								{/if}
							</Field.Content>
						</Field.Field>
						<Field.Field orientation="horizontal">
							<Switch id="ds-pickup" bind:checked={s.pickup_enabled} />
							<Field.Content>
								<Field.Label for="ds-pickup">{m().delivery.offerPickup}</Field.Label>
								<Field.Description>
									{m().delivery.offerPickupHint}
									{m().delivery.pickupLocationsCount({ n: settings.pickup_locations })} ·
									<a href="/merchant/store#locations" class="underline underline-offset-2"
										>{m().delivery.managePickupPoints}</a
									>
								</Field.Description>
								{#if s.pickup_enabled && settings.pickup_locations === 0}
									<Field.Description class="text-warning"
										>{m().delivery.noPickupPoints}</Field.Description
									>
								{/if}
							</Field.Content>
						</Field.Field>
						<FormField
							label={m().delivery.preparationMinutes}
							id="ds-prep"
							error={settingsForm.errors.pickup_preparation_minutes}
							class="max-w-xs"
						>
							{#snippet children({ id, invalid })}<Input
									{id}
									type="number"
									min={0}
									max={43200}
									inputmode="numeric"
									dir="ltr"
									bind:value={s.pickup_preparation_minutes}
									aria-invalid={invalid || undefined}
								/>{/snippet}
						</FormField>
						<FormField
							label={m().delivery.policy}
							id="ds-policy"
							hint={m().delivery.policyHint}
							optional
						>
							{#snippet children({ id, describedBy })}<Textarea
									{id}
									rows={3}
									bind:value={s.delivery_policy}
									aria-describedby={describedBy}
								/>{/snippet}
						</FormField>
						{#if settingsForm.message}<Alert.Root variant="destructive"
								><Alert.Description>{settingsForm.message}</Alert.Description></Alert.Root
							>{/if}
					</Field.Group>
				</Card.Content>
				<Card.Footer class="mt-6">
					<Button type="submit" disabled={settingsForm.pending}
						>{#if settingsForm.pending}<Spinner data-icon="inline-start" />{/if}{m().common
							.save}</Button
					>
				</Card.Footer>
			</form>
		</Card.Root>

		<Card.Root class="h-fit">
			<Card.Header>
				<Card.Title role="heading" aria-level={2}>{m().delivery.moneyTitle}</Card.Title>
			</Card.Header>
			<Card.Content class="flex flex-col gap-3 text-sm text-ink-2">
				<p>{m().delivery.moneyMerchant}</p>
				<p>
					{settings.commission_applies_to === 'ITEMS_AND_DELIVERY'
						? m().delivery.moneyCommission({ rate: fmt.percent(settings.delivery_commission_rate) })
						: m().delivery.moneyNoCommission}
				</p>
				<dl class="grid grid-cols-2 gap-x-4 gap-y-1">
					<dt class="text-ink-3">{m().delivery.feeRecipient}</dt>
					<dd>
						{m().delivery.party[settings.fee_recipient as 'MERCHANT'] ?? settings.fee_recipient}
					</dd>
					<dt class="text-ink-3">{m().delivery.costBearer}</dt>
					<dd>{m().delivery.party[settings.cost_bearer as 'MERCHANT'] ?? settings.cost_bearer}</dd>
				</dl>
			</Card.Content>
		</Card.Root>
	</div>

	<section class="flex flex-col gap-4" aria-labelledby="zones-h">
		<div class="flex flex-wrap items-end justify-between gap-3">
			<div class="flex flex-col gap-1">
				<h2 id="zones-h" class="type-title">{m().delivery.zones}</h2>
				<p class="max-w-2xl text-sm text-ink-2">{m().delivery.zonesHint}</p>
			</div>
			<Button onclick={() => edit(null)} data-testid="add-zone"
				><PlusIcon data-icon="inline-start" />{m().delivery.addZone}</Button
			>
		</div>
		{#if data.zones.length}
			<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head>{m().delivery.zoneName}</Table.Head>
							<Table.Head>{m().delivery.coverage}</Table.Head>
							<Table.Head class="text-end">{m().delivery.fee}</Table.Head>
							<Table.Head class="text-end">{m().delivery.thresholdSar}</Table.Head>
							<Table.Head>{m().delivery.title}</Table.Head>
							<Table.Head><span class="sr-only">{m().common.edit}</span></Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each data.zones as zone (zone.id)}
							<Table.Row data-testid="zone-row">
								<Table.Cell class="font-medium">
									<bdi>{zone.name}</bdi>
									{#if !zone.is_active}<StatusBadge status="INACTIVE" class="ms-2" />{/if}
								</Table.Cell>
								<Table.Cell class="max-w-72 whitespace-normal text-ink-2"
									>{coverage(zone)}</Table.Cell
								>
								<Table.Cell class="text-end tabular"
									>{zone.fee === 0 ? m().delivery.free : fmt.money(zone.fee)}</Table.Cell
								>
								<Table.Cell class="text-end tabular"
									>{zone.free_delivery_threshold != null
										? fmt.money(zone.free_delivery_threshold)
										: '—'}</Table.Cell
								>
								<Table.Cell class="text-ink-2"
									>{etaRange(zone.eta_min_minutes, zone.eta_max_minutes, locale())}</Table.Cell
								>
								<Table.Cell class="text-end whitespace-nowrap">
									<Button
										size="icon-sm"
										variant="ghost"
										onclick={() => edit(zone)}
										aria-label="{m().common.edit}: {zone.name}"><PencilIcon /></Button
									>
									<Button
										size="icon-sm"
										variant="ghost"
										onclick={() => remove(zone)}
										aria-label="{m().common.delete}: {zone.name}"><Trash2Icon /></Button
									>
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</div>
		{:else}
			<EmptyState icon={MapPinnedIcon} title={m().delivery.noZones}>
				<Button onclick={() => edit(null)}
					><PlusIcon data-icon="inline-start" />{m().delivery.addZone}</Button
				>
			</EmptyState>
		{/if}
	</section>
</div>

<Dialog.Root bind:open>
	<Dialog.Content class="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
		<form class="grid gap-4" onsubmit={saveZone} novalidate>
			<Dialog.Header>
				<Dialog.Title>{editing ? m().delivery.editZone : m().delivery.addZone}</Dialog.Title>
				<Dialog.Description>{m().delivery.zonesHint}</Dialog.Description>
			</Dialog.Header>
			<Field.Group class="grid gap-4 sm:grid-cols-2">
				<FormField label={m().delivery.zoneName} id="z-name" error={zoneForm.errors.name}>
					{#snippet children({ id, invalid })}<Input
							{id}
							bind:value={z.name}
							maxlength={100}
							aria-invalid={invalid || undefined}
						/>{/snippet}
				</FormField>
				<FormField label={m().delivery.region} id="z-region" error={zoneForm.errors.region}>
					{#snippet children({ id, invalid })}
						<NativeSelect.Root
							{id}
							bind:value={z.region}
							class="w-full"
							aria-invalid={invalid || undefined}
						>
							<NativeSelect.Option value="">{m().delivery.allRegions}</NativeSelect.Option>
							{#each REGIONS as r (r.key)}
								<NativeSelect.Option value={r.key}>{r[locale()]}</NativeSelect.Option>
							{/each}
						</NativeSelect.Root>
					{/snippet}
				</FormField>
				{#if z.region}
					<FormField
						label={m().delivery.cities}
						id="z-cities"
						hint={m().delivery.citiesHint}
						error={zoneForm.errors.cities}
						optional
						class="sm:col-span-2"
					>
						{#snippet children({ id, invalid, describedBy })}<Input
								{id}
								bind:value={z.cities}
								aria-invalid={invalid || undefined}
								aria-describedby={describedBy}
							/>{/snippet}
					</FormField>
					<FormField
						label={m().delivery.districts}
						id="z-districts"
						hint={m().delivery.districtsHint}
						error={zoneForm.errors.districts}
						optional
						class="sm:col-span-2"
					>
						{#snippet children({ id, invalid, describedBy })}<Input
								{id}
								bind:value={z.districts}
								disabled={!z.cities.trim()}
								aria-invalid={invalid || undefined}
								aria-describedby={describedBy}
							/>{/snippet}
					</FormField>
				{/if}
				<FormField label={m().delivery.feeSar} id="z-fee" error={zoneForm.errors.fee}>
					{#snippet children({ id, invalid })}<Input
							{id}
							inputmode="decimal"
							dir="ltr"
							bind:value={z.fee}
							aria-invalid={invalid || undefined}
						/>{/snippet}
				</FormField>
				<FormField
					label={m().delivery.thresholdSar}
					id="z-threshold"
					hint={m().delivery.thresholdHint}
					error={zoneForm.errors.free_delivery_threshold}
					optional
				>
					{#snippet children({ id, invalid, describedBy })}<Input
							{id}
							inputmode="decimal"
							dir="ltr"
							bind:value={z.threshold}
							aria-invalid={invalid || undefined}
							aria-describedby={describedBy}
						/>{/snippet}
				</FormField>
				<FormField
					label={m().delivery.etaFrom}
					id="z-eta-min"
					error={zoneForm.errors.eta_min_minutes}
				>
					{#snippet children({ id, invalid })}<Input
							{id}
							type="number"
							min={0}
							step="0.5"
							inputmode="decimal"
							dir="ltr"
							bind:value={z.etaMin}
							aria-invalid={invalid || undefined}
						/>{/snippet}
				</FormField>
				<FormField
					label={m().delivery.etaTo}
					id="z-eta-max"
					error={zoneForm.errors.eta_max_minutes}
				>
					{#snippet children({ id, invalid })}<Input
							{id}
							type="number"
							min={0}
							step="0.5"
							inputmode="decimal"
							dir="ltr"
							bind:value={z.etaMax}
							aria-invalid={invalid || undefined}
						/>{/snippet}
				</FormField>
				<Field.Field orientation="horizontal" class="sm:col-span-2">
					<Switch id="z-active" bind:checked={z.active} />
					<Field.Label for="z-active">{m().delivery.zoneActive}</Field.Label>
				</Field.Field>
				{#if zoneForm.message}<Alert.Root variant="destructive" class="sm:col-span-2"
						><Alert.Description>{zoneForm.message}</Alert.Description></Alert.Root
					>{/if}
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (open = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={zoneForm.pending}
					>{#if zoneForm.pending}<Spinner data-icon="inline-start" />{/if}{m().common.save}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
