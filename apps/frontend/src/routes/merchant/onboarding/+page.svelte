<script lang="ts">
	import { invalidate } from '$app/navigation';
	import SendIcon from '@lucide/svelte/icons/send';
	import { api, call } from '#lib/api/client.js';
	import type { BusinessType } from '#lib/api/types.js';
	import AddressFields from '#lib/components/app/AddressFields.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { normalizeSaudiMobile } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m, pick, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const o = $derived(data.onboarding);
	const editable = $derived(['DRAFT', 'ADDITIONAL_INFO_REQUIRED'].includes(o.status));
	const TYPES: BusinessType[] = [
		'freelancer',
		'establishment',
		'company',
		'foreign_company',
		'government',
		'charity'
	];
	const form = new FormState();
	let submitting = $state(false);

	const blankAddr = {
		region: '',
		city: '',
		district: '',
		street: '',
		building_number: '',
		postal_code: ''
	};
	let v = $state({
		business_name: '',
		business_type: 'establishment' as BusinessType,
		category_id: '',
		business_description: '',
		contact_email: '',
		contact_phone: '',
		website: '',
		commercial_registration_number: '',
		vat_number: '',
		address: { ...blankAddr }
	});

	$effect.pre(() => {
		const primary = o.addresses.find((a) => a.is_primary) ?? o.addresses[0];
		v = {
			business_name: o.business_name,
			business_type: o.business_type as BusinessType,
			category_id: o.category_id ?? '',
			business_description: o.business_description,
			contact_email: o.contact_email,
			contact_phone: o.contact_phone,
			website: o.website ?? '',
			commercial_registration_number: o.commercial_registration_number ?? '',
			vat_number: o.vat_number ?? '',
			address: primary
				? {
						region: primary.region,
						city: primary.city,
						district: primary.district ?? '',
						street: primary.street ?? '',
						building_number: primary.building_number ?? '',
						postal_code: primary.postal_code ?? ''
					}
				: { ...blankAddr }
		};
	});

	async function save(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const phone = normalizeSaudiMobile(v.contact_phone);
		if (!phone) return form.fail('contact_phone', m().errors.invalidPhone);
		const res = await form.submit(
			() =>
				call(
					api.PATCH('/api/v1/merchants/onboarding', {
						body: {
							...v,
							contact_phone: phone,
							category_id: v.category_id || null,
							website: v.website || null,
							commercial_registration_number: v.commercial_registration_number || null,
							vat_number: v.vat_number || null,
							address: v.address.region && v.address.city ? v.address : null
						}
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) await Promise.all([invalidate('app:onboarding'), invalidate('app:merchant')]);
	}

	async function submitForReview() {
		submitting = true;
		const ok = await action(
			() => call(api.POST('/api/v1/merchants/onboarding/submit')),
			m().merchant.submitted
		);
		submitting = false;
		if (ok) await Promise.all([invalidate('app:onboarding'), invalidate('app:merchant')]);
	}
</script>

<svelte:head><title>{m().merchant.onboardingTitle} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={m().merchant.onboardingTitle} description={m().merchant.onboardingIntro}>
		{#snippet meta()}<StatusBadge status={o.status} />{/snippet}
		{#snippet actions()}
			{#if editable}
				<Button onclick={submitForReview} disabled={submitting} data-testid="submit-review"
					>{#if submitting}<Spinner data-icon="inline-start" />{:else}<SendIcon
							class="rtl-flip"
							data-icon="inline-start"
						/>{/if}{m().merchant.submitForReview}</Button
				>
			{/if}
		{/snippet}
	</PageHeader>

	{#if o.status_reason}
		<Alert.Root variant="warning">
			<Alert.Title>{m().common.note}</Alert.Title>
			<Alert.Description>{o.status_reason}</Alert.Description>
		</Alert.Root>
	{/if}

	<div class="grid gap-8 xl:grid-cols-[1fr_20rem]">
		<form onsubmit={save} novalidate>
			<Card.Root>
				<Card.Content>
					<Field.Set disabled={!editable} data-disabled={!editable || undefined}>
						<Field.Group>
							<div class="grid gap-4 sm:grid-cols-2">
								<FormField
									label={m().sell.businessName}
									id="o-name"
									error={form.errors.business_name}
								>
									{#snippet children({ id, invalid })}<Input
											{id}
											bind:value={v.business_name}
											aria-invalid={invalid || undefined}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().sell.businessType}
									id="o-type"
									error={form.errors.business_type}
								>
									{#snippet children({ id })}
										<NativeSelect.Root {id} bind:value={v.business_type} class="w-full">
											{#each TYPES as t (t)}<NativeSelect.Option value={t}
													>{m().businessTypes[t]}</NativeSelect.Option
												>{/each}
										</NativeSelect.Root>
									{/snippet}
								</FormField>
								<FormField label={m().sell.category} id="o-cat" error={form.errors.category_id}>
									{#snippet children({ id })}
										<NativeSelect.Root {id} bind:value={v.category_id} class="w-full">
											<NativeSelect.Option value="">{m().common.none}</NativeSelect.Option>
											{#each data.categories.filter((c) => !c.parent_id) as c (c.id)}<NativeSelect.Option
													value={c.id}>{pick(c, 'name')}</NativeSelect.Option
												>{/each}
										</NativeSelect.Root>
									{/snippet}
								</FormField>
								<FormField
									label={m().merchant.website}
									id="o-web"
									error={form.errors.website}
									optional
								>
									{#snippet children({ id, invalid })}<Input
											{id}
											type="url"
											dir="ltr"
											bind:value={v.website}
											placeholder="https://"
											aria-invalid={invalid || undefined}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().merchant.contactEmail}
									id="o-email"
									error={form.errors.contact_email}
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
									id="o-phone"
									error={form.errors.contact_phone}
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
									label={m().sell.crNumber}
									id="o-cr"
									error={form.errors.commercial_registration_number}
									hint={m().ui.crFormat}
								>
									{#snippet children({ id, invalid, describedBy })}<Input
											{id}
											dir="ltr"
											inputmode="numeric"
											maxlength={10}
											bind:value={v.commercial_registration_number}
											aria-invalid={invalid || undefined}
											aria-describedby={describedBy}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().sell.vatNumber}
									id="o-vat"
									error={form.errors.vat_number}
									hint={m().ui.vatFormat}
									optional
								>
									{#snippet children({ id, invalid, describedBy })}<Input
											{id}
											dir="ltr"
											inputmode="numeric"
											maxlength={15}
											bind:value={v.vat_number}
											aria-invalid={invalid || undefined}
											aria-describedby={describedBy}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().sell.description}
									id="o-desc"
									error={form.errors.business_description}
									class="sm:col-span-2"
								>
									{#snippet children({ id })}<Textarea
											{id}
											rows={4}
											bind:value={v.business_description}
										/>{/snippet}
								</FormField>
							</div>
							<Field.Set>
								<Field.Legend variant="label">{m().merchant.address}</Field.Legend>
								<AddressFields
									bind:value={v.address}
									errors={form.errors}
									errorPrefix="address."
									idPrefix="o-addr"
								/>
							</Field.Set>
						</Field.Group>
					</Field.Set>
				</Card.Content>
				{#if editable}
					<Card.Footer>
						<Button type="submit" variant="secondary" disabled={form.pending}
							>{#if form.pending}<Spinner data-icon="inline-start" />{m().common.saving}{:else}{m()
									.common.save}{/if}</Button
						>
					</Card.Footer>
				{/if}
			</Card.Root>
		</form>

		<aside class="h-fit">
			<Card.Root class="h-full">
				<Card.Header>
					<Card.Title role="heading" aria-level={2}>{m().merchant.verificationHistory}</Card.Title>
				</Card.Header>
				<Card.Content class="flex flex-col gap-4">
					{#if data.history.length}
						<ol class="flex flex-col gap-4 border-s border-line ps-4">
							{#each data.history as h, i (i)}
								<li class="flex flex-col gap-1">
									<p class="text-sm font-medium">{statusLabel(h.to_status)}</p>
									<p class="text-xs text-ink-3">{fmt.datetime(h.created_at)}</p>
									{#if h.note}<p class="text-sm text-ink-2"><bdi>{h.note}</bdi></p>{/if}
								</li>
							{/each}
						</ol>
					{:else}
						<p class="text-sm text-ink-3">—</p>
					{/if}
				</Card.Content>
			</Card.Root>
		</aside>
	</div>
</div>
