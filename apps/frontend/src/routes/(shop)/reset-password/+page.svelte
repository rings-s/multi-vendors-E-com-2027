<script lang="ts">
	import { page } from '$app/state';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import { api, call } from '#lib/api/client.js';
	import AuthCard from '#lib/components/app/AuthCard.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { m } from '#lib/i18n/state.svelte.js';

	const token = $derived(page.url.searchParams.get('token') ?? '');
	const form = new FormState();
	let password = $state('');
	let done = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		if (password.length < 10) return form.fail('new_password', m().auth.passwordHint);
		const res = await form.submit(() =>
			call(
				api.POST('/api/v1/auth/password-reset/confirm', { body: { token, new_password: password } })
			)
		);
		if (res.ok) done = true;
	}
</script>

<svelte:head><title>{m().auth.resetTitle} · {m().brand.name}</title></svelte:head>

<AuthCard title={m().auth.resetTitle}>
	{#if !token}
		<Empty.Root class="p-0" role="alert">
			<Empty.Header>
				<Empty.Description>{m().auth.resetMissingToken}</Empty.Description>
			</Empty.Header>
			<Empty.Content><Button href="/forgot-password">{m().auth.sendLink}</Button></Empty.Content>
		</Empty.Root>
	{:else if done}
		<Empty.Root class="p-0" role="status">
			<Empty.Header>
				<Empty.Media variant="icon"><CircleCheckIcon /></Empty.Media>
				<Empty.Description>{m().auth.resetDone}</Empty.Description>
			</Empty.Header>
			<Empty.Content><Button href="/sign-in">{m().auth.signIn}</Button></Empty.Content>
		</Empty.Root>
	{:else}
		<form onsubmit={submit} novalidate>
			<Field.Group>
				{#if form.message}<Alert.Root variant="destructive"
						><Alert.Description>{form.message}</Alert.Description></Alert.Root
					>{/if}
				<FormField
					label={m().auth.newPassword}
					id="new_password"
					error={form.errors.new_password}
					hint={m().auth.passwordHint}
				>
					{#snippet children({ id, invalid, describedBy })}
						<Input
							{id}
							type="password"
							bind:value={password}
							autocomplete="new-password"
							minlength={10}
							required
							aria-invalid={invalid || undefined}
							aria-describedby={describedBy}
						/>
					{/snippet}
				</FormField>
				<Button type="submit" size="lg" class="w-full" disabled={form.pending}>
					{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().common.save}
				</Button>
			</Field.Group>
		</form>
	{/if}
</AuthCard>
