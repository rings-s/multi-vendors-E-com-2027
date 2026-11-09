<script lang="ts">
	import { page } from '$app/state';
	import { api, call } from '#lib/api/client.js';
	import { safeNext } from '#lib/auth.js';
	import AuthCard from '#lib/components/app/AuthCard.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { normalizeSaudiMobile } from '#lib/format.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { locale, m } from '#lib/i18n/state.svelte.js';
	import { afterSignIn } from '#lib/session.js';

	const form = new FormState();
	let fullName = $state('');
	let email = $state('');
	let phone = $state('');
	let password = $state('');
	const next = $derived(page.url.searchParams.get('next'));

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const mobile = phone.trim() ? normalizeSaudiMobile(phone) : null;
		if (phone.trim() && !mobile) form.fail('phone', m().errors.invalidPhone);
		if (password.length < 10) form.fail('password', m().auth.passwordHint);
		if (form.hasErrors) return;
		const res = await form.submit(
			() =>
				call(
					api.POST('/api/v1/auth/register', {
						body: {
							full_name: fullName,
							email,
							password,
							phone: mobile,
							preferred_language: locale()
						}
					})
				),
			{ toastError: false }
		);
		if (res.ok) await afterSignIn(safeNext(next, '/account'));
	}
</script>

<svelte:head><title>{m().nav.signUp} · {m().brand.name}</title></svelte:head>

<AuthCard title={m().auth.signUpTitle} subtitle={m().auth.signUpSubtitle}>
	<form onsubmit={submit} novalidate>
		<Field.Group>
			{#if form.message}
				<Alert.Root variant="destructive"
					><Alert.Description>{form.message}</Alert.Description></Alert.Root
				>
			{/if}
			<FormField label={m().auth.fullName} id="full_name" error={form.errors.full_name}>
				{#snippet children({ id, invalid })}
					<Input
						{id}
						bind:value={fullName}
						autocomplete="name"
						required
						minlength={2}
						aria-invalid={invalid || undefined}
					/>
				{/snippet}
			</FormField>
			<FormField label={m().auth.email} id="email" error={form.errors.email}>
				{#snippet children({ id, invalid })}
					<Input
						{id}
						type="email"
						bind:value={email}
						autocomplete="email"
						dir="ltr"
						required
						aria-invalid={invalid || undefined}
					/>
				{/snippet}
			</FormField>
			<FormField
				label={m().auth.phone}
				id="phone"
				error={form.errors.phone}
				hint={m().auth.phoneHint}
				optional
			>
				{#snippet children({ id, invalid, describedBy })}
					<Input
						{id}
						type="tel"
						inputmode="tel"
						bind:value={phone}
						autocomplete="tel"
						dir="ltr"
						aria-invalid={invalid || undefined}
						aria-describedby={describedBy}
					/>
				{/snippet}
			</FormField>
			<FormField
				label={m().auth.password}
				id="password"
				error={form.errors.password}
				hint={m().auth.passwordHint}
			>
				{#snippet children({ id, invalid, describedBy })}
					<Input
						{id}
						type="password"
						bind:value={password}
						autocomplete="new-password"
						required
						minlength={10}
						aria-invalid={invalid || undefined}
						aria-describedby={describedBy}
					/>
				{/snippet}
			</FormField>
			<Button type="submit" size="lg" class="w-full" disabled={form.pending}>
				{#if form.pending}<Spinner data-icon="inline-start" />{m().auth.signingUp}{:else}{m().auth
						.signUp}{/if}
			</Button>
		</Field.Group>
	</form>
	{#snippet footer()}
		<p>
			{m().auth.haveAccount}
			<a class="font-medium text-primary hover:underline" href="/sign-in">{m().auth.signIn}</a>
		</p>
		<p>
			{m().auth.sellerPrompt}
			<a class="font-medium text-primary hover:underline" href="/sell">{m().auth.sellerLink}</a>
		</p>
	{/snippet}
</AuthCard>
