<script lang="ts">
	import { invalidate } from '$app/navigation';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import { api, call } from '#lib/api/client.js';
	import type { Address } from '#lib/api/types.js';
	import AddressFields, { addressBody } from '#lib/components/app/AddressFields.svelte';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { normalizeSaudiMobile } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const blank = () => ({
		label: '',
		recipient_name: '',
		phone: '',
		region: '',
		city: '',
		district: '',
		street: '',
		building_number: '',
		postal_code: '',
		additional_info: '',
		delivery_instructions: '',
		latitude: null as number | null,
		longitude: null as number | null,
		is_default: false
	});

	let open = $state(false);
	let editing = $state<Address | null>(null);
	let value = $state(blank());
	const form = new FormState();
	const refresh = () => invalidate('app:addresses');

	function edit(a: Address | null) {
		editing = a;
		value = a ? { ...blank(), ...a } : { ...blank(), is_default: data.addresses.length === 0 };
		form.reset();
		open = true;
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const phone = normalizeSaudiMobile(value.phone);
		if (!phone) return form.fail('phone', m().errors.invalidPhone);
		const body = addressBody({ ...value, phone });
		const res = await form.submit(
			() =>
				editing
					? call(
							api.PATCH('/api/v1/customers/addresses/{address_id}', {
								params: { path: { address_id: editing.id } },
								body: { ...body, clear_location: editing.latitude != null && body.latitude == null }
							})
						)
					: call(api.POST('/api/v1/customers/addresses', { body })),
			{ success: m().common.saved }
		);
		if (res.ok) {
			open = false;
			await refresh();
		}
	}

	async function remove(a: Address) {
		if (
			!(await confirm({
				title: m().account.deleteAddressConfirm,
				destructive: true,
				confirmLabel: m().common.delete
			}))
		)
			return;
		await action(() =>
			call(
				api.DELETE('/api/v1/customers/addresses/{address_id}', {
					params: { path: { address_id: a.id } }
				})
			)
		);
		await refresh();
	}

	async function makeDefault(a: Address) {
		await action(
			() =>
				call(
					api.PATCH('/api/v1/customers/addresses/{address_id}', {
						params: { path: { address_id: a.id } },
						body: { is_default: true, clear_location: false }
					})
				),
			m().common.saved
		);
		await refresh();
	}
</script>

<svelte:head><title>{m().account.addresses} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().account.addresses}>
		{#snippet actions()}<Button onclick={() => edit(null)}
				><PlusIcon data-icon="inline-start" />{m().account.newAddress}</Button
			>{/snippet}
	</PageHeader>

	{#if data.addresses.length}
		<ul class="grid gap-4 md:grid-cols-2">
			{#each data.addresses as a (a.id)}
				<li>
					<Card.Root class="h-full">
						<Card.Content class="flex flex-col justify-between gap-4">
							<div class="flex flex-col gap-1 text-sm">
								<p class="flex items-center gap-2 font-medium text-ink">
									{a.label || a.recipient_name}
									{#if a.is_default}<Badge variant="brand">{m().account.defaultAddress}</Badge>{/if}
								</p>
								<p class="text-ink-2">
									<bdi>{a.recipient_name}</bdi> ·
									<span dir="ltr" class="tabular">{fmt.phone(a.phone)}</span>
								</p>
								<p class="text-ink-3">
									{fmt.list([
										a.street,
										a.building_number,
										a.district,
										a.city,
										fmt.region(a.region),
										a.postal_code
									])}
								</p>
							</div>
							<div class="flex flex-wrap gap-2">
								<Button size="sm" variant="outline" onclick={() => edit(a)}
									><PencilIcon data-icon="inline-start" />{m().common.edit}</Button
								>
								{#if !a.is_default}<Button size="sm" variant="ghost" onclick={() => makeDefault(a)}
										>{m().account.makeDefault}</Button
									>{/if}
								<Button
									size="icon-sm"
									variant="destructive"
									onclick={() => remove(a)}
									aria-label="{m().common.delete}: {a.label || a.recipient_name}"
									><Trash2Icon /></Button
								>
							</div>
						</Card.Content>
					</Card.Root>
				</li>
			{/each}
		</ul>
	{:else}
		<EmptyState icon={MapPinIcon} title={m().account.noAddresses}>
			<Button onclick={() => edit(null)}
				><PlusIcon data-icon="inline-start" />{m().account.newAddress}</Button
			>
		</EmptyState>
	{/if}
</div>

<Dialog.Root bind:open>
	<Dialog.Content class="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
		<form class="grid gap-4" onsubmit={save} novalidate>
			<Dialog.Header
				><Dialog.Title>{editing ? m().account.editAddress : m().account.newAddress}</Dialog.Title
				></Dialog.Header
			>
			<Field.Group>
				<div class="grid gap-4 sm:grid-cols-3">
					<FormField
						label={m().account.addressLabel}
						id="a-label"
						hint={m().account.addressLabelHint}
						optional
						error={form.errors.label}
					>
						{#snippet children({ id })}<Input {id} bind:value={value.label} />{/snippet}
					</FormField>
					<FormField
						label={m().account.recipient}
						id="a-recipient"
						error={form.errors.recipient_name}
					>
						{#snippet children({ id, invalid })}<Input
								{id}
								bind:value={value.recipient_name}
								autocomplete="name"
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField label={m().auth.phone} id="a-phone" error={form.errors.phone}>
						{#snippet children({ id, invalid })}<Input
								{id}
								type="tel"
								dir="ltr"
								bind:value={value.phone}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
				</div>
				<AddressFields bind:value errors={form.errors} idPrefix="a" detectLocation />
				<FormField
					label={m().account.additionalInfo}
					id="a-info"
					optional
					error={form.errors.additional_info}
				>
					{#snippet children({ id })}<Input {id} bind:value={value.additional_info} />{/snippet}
				</FormField>
				<FormField
					label={m().delivery.addressInstructions}
					id="a-instructions"
					hint={m().delivery.instructionsHint}
					optional
					error={form.errors.delivery_instructions}
				>
					{#snippet children({ id, describedBy })}<Textarea
							{id}
							rows={2}
							maxlength={500}
							bind:value={value.delivery_instructions}
							aria-describedby={describedBy}
						/>{/snippet}
				</FormField>
				<Field.Field orientation="horizontal">
					<Checkbox id="a-default" bind:checked={value.is_default} />
					<Field.Label for="a-default" class="font-normal">{m().account.defaultAddress}</Field.Label
					>
				</Field.Field>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (open = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().common.save}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
