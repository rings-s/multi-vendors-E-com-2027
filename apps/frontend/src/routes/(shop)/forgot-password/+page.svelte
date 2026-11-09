<script lang="ts">
	import MailCheckIcon from '@lucide/svelte/icons/mail-check';
	import { api, call } from '#lib/api/client.js';
	import AuthCard from '#lib/components/app/AuthCard.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { m } from '#lib/i18n/state.svelte.js';

	const form = new FormState();
	let email = $state('');
	let sent = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		const res = await form.submit(() =>
			call(api.POST('/api/v1/auth/password-reset/request', { body: { email } }))
		);
		if (res.ok) sent = true;
	}
</script>

<svelte:head><title>{m().auth.forgotTitle} · {m().brand.name}</title></svelte:head>

<AuthCard title={m().auth.forgotTitle} subtitle={sent ? undefined : m().auth.forgotBody}>
	{#if sent}
		<Empty.Root class="p-0" role="status">
			<Empty.Header>
				<Empty.Media variant="icon"><MailCheckIcon /></Empty.Media>
				<Empty.Description>{m().auth.linkSent}</Empty.Description>
			</Empty.Header>
		</Empty.Root>
	{:else}
		<form onsubmit={submit} novalidate>
			<Field.Group>
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
				<Button type="submit" size="lg" class="w-full" disabled={form.pending}>
					{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().auth.sendLink}
				</Button>
			</Field.Group>
		</form>
	{/if}
	{#snippet footer()}
		<a class="font-medium text-primary hover:underline" href="/sign-in">{m().auth.signIn}</a>
	{/snippet}
</AuthCard>
