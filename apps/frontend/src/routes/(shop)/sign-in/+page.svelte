<script lang="ts">
	import { page } from '$app/state';
	import { api, call } from '#lib/api/client.js';
	import { homeFor, safeNext } from '#lib/auth.js';
	import AuthCard from '#lib/components/app/AuthCard.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { afterSignIn } from '#lib/session.js';

	const form = new FormState();
	let email = $state('');
	let password = $state('');
	const next = $derived(page.url.searchParams.get('next'));

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		const res = await form.submit(
			() => call(api.POST('/api/v1/auth/login', { body: { email, password } })),
			{ toastError: false }
		);
		if (res.ok) await afterSignIn(safeNext(next, homeFor(res.data.user)));
	}
</script>

<svelte:head><title>{m().nav.signIn} · {m().brand.name}</title></svelte:head>

<AuthCard title={m().auth.signInTitle} subtitle={m().auth.signInSubtitle}>
	<form onsubmit={submit} novalidate>
		<Field.Group>
			{#if form.message}
				<Alert.Root variant="destructive" data-testid="form-error"
					><Alert.Description>{form.message}</Alert.Description></Alert.Root
				>
			{/if}
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
			<FormField label={m().auth.password} id="password" error={form.errors.password}>
				{#snippet children({ id, invalid })}
					<Input
						{id}
						type="password"
						bind:value={password}
						autocomplete="current-password"
						required
						aria-invalid={invalid || undefined}
					/>
				{/snippet}
			</FormField>
			<div class="flex justify-end">
				<a href="/forgot-password" class="text-sm text-ink-2 underline-offset-4 hover:underline"
					>{m().auth.forgot}</a
				>
			</div>
			<Button type="submit" size="lg" class="w-full" disabled={form.pending}>
				{#if form.pending}<Spinner data-icon="inline-start" />{m().auth.signingIn}{:else}{m().auth
						.signIn}{/if}
			</Button>
		</Field.Group>
	</form>
	{#snippet footer()}
		<p>
			{m().auth.noAccount}
			<a
				class="font-medium text-primary hover:underline"
				href="/register{next ? `?next=${encodeURIComponent(next)}` : ''}">{m().auth.signUp}</a
			>
		</p>
		<p>
			{m().auth.sellerPrompt}
			<a class="font-medium text-primary hover:underline" href="/sell">{m().auth.sellerLink}</a>
		</p>
	{/snippet}
</AuthCard>
