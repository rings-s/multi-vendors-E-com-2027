<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { page } from '$app/state';
	import { api, call } from '#lib/api/client.js';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { normalizeSaudiMobile } from '#lib/format.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { setLocale } from '#lib/prefs.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const user = $derived(page.data.user!);
	const form = new FormState();
	let fullName = $state('');
	let phone = $state('');
	let language = $state<'ar' | 'en'>('ar');
	let marketing = $state(false);

	$effect.pre(() => {
		fullName = user.full_name;
		phone = user.phone ?? '';
		language = user.preferred_language === 'en' ? 'en' : 'ar';
		marketing = data.customer?.preferences.marketing_emails ?? false;
	});

	async function save(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const mobile = phone.trim() ? normalizeSaudiMobile(phone) : null;
		if (phone.trim() && !mobile) return form.fail('phone', m().errors.invalidPhone);
		const res = await form.submit(
			() =>
				call(
					api.PATCH('/api/v1/users/me', {
						body: { full_name: fullName, phone: mobile, preferred_language: language }
					})
				),
			{ success: m().account.profileSaved }
		);
		if (res.ok) {
			if (language !== page.data.locale) await setLocale(language, true);
			else await invalidateAll();
		}
	}

	async function toggleMarketing(value: boolean) {
		marketing = value;
		await action(
			() =>
				call(api.PATCH('/api/v1/customers/me/preferences', { body: { marketing_emails: value } })),
			m().common.saved
		);
	}
</script>

<svelte:head><title>{m().account.profile} · {m().brand.name}</title></svelte:head>

<div class="flex max-w-2xl flex-col gap-8">
	<PageHeader title={m().account.profile} />
	<form onsubmit={save} novalidate>
		<Card.Root class="h-full">
			<Card.Content>
				<Field.Group>
					<FormField label={m().auth.fullName} id="p-name" error={form.errors.full_name}>
						{#snippet children({ id, invalid })}<Input
								{id}
								bind:value={fullName}
								autocomplete="name"
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField label={m().auth.email} id="p-email">
						{#snippet children({ id })}<Input
								{id}
								value={user.email}
								disabled
								dir="ltr"
							/>{/snippet}
					</FormField>
					<FormField
						label={m().auth.phone}
						id="p-phone"
						error={form.errors.phone}
						hint={m().auth.phoneHint}
						optional
					>
						{#snippet children({ id, invalid, describedBy })}<Input
								{id}
								type="tel"
								dir="ltr"
								bind:value={phone}
								aria-invalid={invalid || undefined}
								aria-describedby={describedBy}
							/>{/snippet}
					</FormField>
					<FormField label={m().auth.preferredLanguage} id="p-lang">
						{#snippet children({ id })}
							<NativeSelect.Root {id} bind:value={language}>
								<NativeSelect.Option value="ar">العربية</NativeSelect.Option>
								<NativeSelect.Option value="en">English</NativeSelect.Option>
							</NativeSelect.Root>
						{/snippet}
					</FormField>
				</Field.Group>
			</Card.Content>
			<Card.Footer>
				<Button type="submit" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{m().common.saving}{:else}{m()
							.common.save}{/if}</Button
				>
			</Card.Footer>
		</Card.Root>
	</form>

	{#if data.customer}
		<section>
			<Card.Root class="h-full">
				<Card.Header>
					<Card.Title role="heading" aria-level={2}>{m().account.preferences}</Card.Title>
				</Card.Header>
				<Card.Content>
					<Field.Group>
						<Field.Field orientation="horizontal">
							<Field.Label for="p-marketing" class="font-normal"
								>{m().account.marketingEmails}</Field.Label
							>
							<Switch id="p-marketing" checked={marketing} onCheckedChange={toggleMarketing} />
						</Field.Field>
					</Field.Group>
				</Card.Content>
			</Card.Root>
		</section>
	{/if}
</div>
