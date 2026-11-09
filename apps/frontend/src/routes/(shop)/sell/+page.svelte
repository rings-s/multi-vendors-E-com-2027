<script lang="ts">
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import CheckIcon from '@lucide/svelte/icons/check';
	import { api, call } from '#lib/api/client.js';
	import type { BusinessType } from '#lib/api/types.js';
	import AddressFields from '#lib/components/app/AddressFields.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as InputGroup from '#lib/components/ui/input-group/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { normalizeSaudiMobile } from '#lib/format.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { locale, m, pick } from '#lib/i18n/state.svelte.js';
	import { afterSignIn } from '#lib/session.js';
	import { cn } from '#lib/utils.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const form = new FormState();
	let step = $state(0);
	const v = $state({
		owner_full_name: '',
		email: '',
		password: '',
		mobile: '',
		business_name: '',
		business_type: 'establishment' as BusinessType,
		category_id: '',
		business_description: '',
		commercial_registration_number: '',
		vat_number: '',
		store_name: '',
		store_slug: '',
		address: {
			region: '',
			city: '',
			district: '',
			street: '',
			building_number: '',
			postal_code: ''
		}
	});
	let slugTouched = $state(false);

	const TYPES: BusinessType[] = [
		'freelancer',
		'establishment',
		'company',
		'foreign_company',
		'government',
		'charity'
	];
	const steps = $derived([m().sell.step1, m().sell.step2, m().sell.step3]);
	const FIELD_STEP: Record<string, number> = {
		owner_full_name: 0,
		email: 0,
		password: 0,
		mobile: 0,
		business_name: 1,
		business_type: 1,
		category_id: 1,
		business_description: 1,
		commercial_registration_number: 1,
		vat_number: 1
	};

	function slugify(s: string) {
		return s
			.toLowerCase()
			.normalize('NFKD')
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '')
			.slice(0, 60);
	}
	$effect(() => {
		if (!slugTouched) v.store_slug = slugify(v.store_name);
	});

	function validate(s: number): boolean {
		form.reset();
		const req = (k: string, ok: boolean, msg = m().common.required) => !ok && form.fail(k, msg);
		if (s === 0) {
			req('owner_full_name', v.owner_full_name.trim().length >= 2);
			req('email', /^\S+@\S+\.\S+$/.test(v.email));
			req('password', v.password.length >= 10, m().auth.passwordHint);
			req('mobile', !!normalizeSaudiMobile(v.mobile), m().errors.invalidPhone);
		} else if (s === 1) {
			req('business_name', v.business_name.trim().length >= 2);
			req(
				'commercial_registration_number',
				!v.commercial_registration_number || /^\d{10}$/.test(v.commercial_registration_number),
				m().ui.crFormat
			);
			req('vat_number', !v.vat_number || /^3\d{13}3$/.test(v.vat_number), m().ui.vatFormat);
		} else {
			req('store_name', v.store_name.trim().length >= 2);
			req(
				'store_slug',
				/^[a-z0-9](?:[a-z0-9-]{1,58}[a-z0-9])$/.test(v.store_slug),
				m().sell.storeSlugHint
			);
			req('address.region', !!v.address.region);
			req('address.city', v.address.city.trim().length >= 2);
		}
		return !form.hasErrors;
	}

	function next() {
		if (validate(step)) step = Math.min(2, step + 1);
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (step < 2) return next();
		if (!validate(2)) return;
		const res = await form.submit(() =>
			call(
				api.POST('/api/v1/merchants/register', {
					body: {
						...v,
						mobile: normalizeSaudiMobile(v.mobile)!,
						category_id: v.category_id || null,
						city: v.address.city,
						commercial_registration_number: v.commercial_registration_number || null,
						vat_number: v.vat_number || null,
						preferred_language: locale()
					}
				})
			)
		);
		if (res.ok) await afterSignIn('/merchant');
		else {
			const first = Object.keys(form.errors)[0];
			if (first && FIELD_STEP[first] !== undefined) step = FIELD_STEP[first];
		}
	}
</script>

<svelte:head><title>{m().sell.title} · {m().brand.name}</title></svelte:head>

<div class="container-page grid gap-12 py-12 lg:grid-cols-[1fr_1.3fr] lg:py-20">
	<div class="flex flex-col gap-8 lg:sticky lg:top-28 lg:self-start">
		<div class="flex flex-col gap-4">
			<h1 class="font-display text-4xl leading-tight text-ink sm:text-5xl">{m().sell.title}</h1>
			<p class="text-lg text-ink-2">{m().sell.subtitle}</p>
		</div>
		<ul class="flex flex-col gap-3">
			{#each [m().sell.benefit1, m().sell.benefit2, m().sell.benefit3] as b (b)}
				<li class="flex items-center gap-3 text-ink">
					<span class="grid size-6 place-items-center rounded-full bg-brand-soft text-primary"
						><CheckIcon class="size-3.5" /></span
					>{b}
				</li>
			{/each}
		</ul>
		<p class="text-sm text-ink-3">
			{m().sell.already}
			<a href="/sign-in?next=/merchant" class="font-medium text-primary hover:underline"
				>{m().nav.signIn}</a
			>
		</p>
	</div>

	<form onsubmit={submit} novalidate>
		<Card.Root class="shadow-soft">
			<Card.Content>
				<Field.Group>
					<ol class="flex gap-2" aria-label={m().sell.title}>
						{#each steps as label, i (i)}
							<li class="flex flex-1 flex-col gap-2" aria-current={i === step ? 'step' : undefined}>
								<span
									class={cn('block h-1 rounded-full', i <= step ? 'bg-primary' : 'bg-surface-3')}
								></span>
								<span class={cn('text-xs', i === step ? 'font-medium text-ink' : 'text-ink-3')}
									>{i + 1}. {label}</span
								>
							</li>
						{/each}
					</ol>

					{#if form.message && !form.hasErrors}<Alert.Root variant="destructive"
							><Alert.Description>{form.message}</Alert.Description></Alert.Root
						>{/if}

					{#if step === 0}
						<div class="grid gap-4 sm:grid-cols-2">
							<FormField
								label={m().sell.ownerName}
								id="owner"
								error={form.errors.owner_full_name}
								class="sm:col-span-2"
							>
								{#snippet children({ id, invalid })}<Input
										{id}
										bind:value={v.owner_full_name}
										autocomplete="name"
										aria-invalid={invalid || undefined}
									/>{/snippet}
							</FormField>
							<FormField label={m().auth.email} id="m-email" error={form.errors.email}>
								{#snippet children({ id, invalid })}<Input
										{id}
										type="email"
										dir="ltr"
										bind:value={v.email}
										autocomplete="email"
										aria-invalid={invalid || undefined}
									/>{/snippet}
							</FormField>
							<FormField
								label={m().sell.mobile}
								id="m-mobile"
								error={form.errors.mobile}
								hint={m().auth.phoneHint}
							>
								{#snippet children({ id, invalid, describedBy })}<Input
										{id}
										type="tel"
										dir="ltr"
										bind:value={v.mobile}
										autocomplete="tel"
										aria-invalid={invalid || undefined}
										aria-describedby={describedBy}
									/>{/snippet}
							</FormField>
							<FormField
								label={m().auth.password}
								id="m-password"
								error={form.errors.password}
								hint={m().auth.passwordHint}
								class="sm:col-span-2"
							>
								{#snippet children({ id, invalid, describedBy })}<Input
										{id}
										type="password"
										bind:value={v.password}
										autocomplete="new-password"
										aria-invalid={invalid || undefined}
										aria-describedby={describedBy}
									/>{/snippet}
							</FormField>
						</div>
					{:else if step === 1}
						<div class="grid gap-4 sm:grid-cols-2">
							<FormField
								label={m().sell.businessName}
								id="b-name"
								error={form.errors.business_name}
								class="sm:col-span-2"
							>
								{#snippet children({ id, invalid })}<Input
										{id}
										bind:value={v.business_name}
										autocomplete="organization"
										aria-invalid={invalid || undefined}
									/>{/snippet}
							</FormField>
							<FormField
								label={m().sell.businessType}
								id="b-type"
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
							<FormField
								label={m().sell.category}
								id="b-cat"
								error={form.errors.category_id}
								optional
							>
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
								label={m().sell.crNumber}
								id="b-cr"
								error={form.errors.commercial_registration_number}
								optional
								hint={m().ui.crFormat}
							>
								{#snippet children({ id, invalid, describedBy })}<Input
										{id}
										bind:value={v.commercial_registration_number}
										inputmode="numeric"
										maxlength={10}
										dir="ltr"
										aria-invalid={invalid || undefined}
										aria-describedby={describedBy}
									/>{/snippet}
							</FormField>
							<FormField
								label={m().sell.vatNumber}
								id="b-vat"
								error={form.errors.vat_number}
								optional
								hint={m().ui.vatFormat}
							>
								{#snippet children({ id, invalid, describedBy })}<Input
										{id}
										bind:value={v.vat_number}
										inputmode="numeric"
										maxlength={15}
										dir="ltr"
										aria-invalid={invalid || undefined}
										aria-describedby={describedBy}
									/>{/snippet}
							</FormField>
							<FormField
								label={m().sell.description}
								id="b-desc"
								error={form.errors.business_description}
								optional
								class="sm:col-span-2"
							>
								{#snippet children({ id })}<Textarea
										{id}
										bind:value={v.business_description}
										rows={4}
										maxlength={5000}
									/>{/snippet}
							</FormField>
						</div>
					{:else}
						<div class="flex flex-col gap-4">
							<div class="grid gap-4 sm:grid-cols-2">
								<FormField label={m().sell.storeName} id="s-name" error={form.errors.store_name}>
									{#snippet children({ id, invalid })}<Input
											{id}
											bind:value={v.store_name}
											aria-invalid={invalid || undefined}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().sell.storeSlug}
									id="s-slug"
									error={form.errors.store_slug}
									hint={m().sell.storeSlugHint}
								>
									{#snippet children({ id, invalid, describedBy })}
										<InputGroup.Root dir="ltr">
											<InputGroup.Addon
												><InputGroup.Text>/stores/</InputGroup.Text></InputGroup.Addon
											>
											<InputGroup.Input
												{id}
												bind:value={v.store_slug}
												oninput={() => (slugTouched = true)}
												aria-invalid={invalid || undefined}
												aria-describedby={describedBy}
											/>
										</InputGroup.Root>
									{/snippet}
								</FormField>
							</div>
							<Field.Set class="pt-2">
								<Field.Legend variant="label">{m().merchant.address}</Field.Legend>
								<AddressFields
									bind:value={v.address}
									errors={form.errors}
									errorPrefix="address."
									idPrefix="addr"
								/>
							</Field.Set>
						</div>
					{/if}
				</Field.Group>
			</Card.Content>
			<Card.Footer class="justify-between gap-3">
				{#if step > 0}
					<Button type="button" variant="ghost" onclick={() => (step -= 1)}
						><ArrowLeftIcon class="rtl-flip" data-icon="inline-start" />{m().common.back}</Button
					>
				{:else}<span></span>{/if}
				{#if step < 2}
					<Button type="button" onclick={next}
						>{m().common.next}<ArrowRightIcon class="rtl-flip" data-icon="inline-end" /></Button
					>
				{:else}
					<Button type="submit" disabled={form.pending} data-testid="register-merchant"
						>{#if form.pending}<Spinner data-icon="inline-start" />{m().sell.registering}{:else}{m()
								.sell.register}{/if}</Button
					>
				{/if}
			</Card.Footer>
		</Card.Root>
	</form>
</div>
