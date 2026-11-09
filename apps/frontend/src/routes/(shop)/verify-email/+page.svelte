<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { page } from '$app/state';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import CircleXIcon from '@lucide/svelte/icons/circle-x';
	import MailIcon from '@lucide/svelte/icons/mail';
	import { onMount } from 'svelte';
	import { api, call } from '#lib/api/client.js';
	import AuthCard from '#lib/components/app/AuthCard.svelte';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { action } from '#lib/forms.svelte.js';
	import { m } from '#lib/i18n/state.svelte.js';

	const token = page.url.searchParams.get('token');
	const user = $derived(page.data.user);
	let status = $state<'idle' | 'verifying' | 'ok' | 'failed'>(token ? 'verifying' : 'idle');
	let resending = $state(false);

	onMount(async () => {
		if (!token) return;
		try {
			await call(api.POST('/api/v1/auth/verify-email', { body: { token } }));
			status = 'ok';
			await invalidateAll();
		} catch {
			status = 'failed';
		}
	});

	async function resend() {
		resending = true;
		await action(() => call(api.POST('/api/v1/auth/verify-email/resend')), m().auth.resent);
		resending = false;
	}
</script>

<svelte:head><title>{m().auth.verifyTitle} · {m().brand.name}</title></svelte:head>

<AuthCard title={m().auth.verifyTitle}>
	<Empty.Root class="p-0" aria-live="polite">
		{#if status === 'verifying'}
			<Empty.Header>
				<Empty.Media><Spinner class="size-8 text-primary" /></Empty.Media>
				<Empty.Description>{m().auth.verifying}</Empty.Description>
			</Empty.Header>
		{:else if status === 'ok' || (status === 'idle' && user?.email_verified)}
			<Empty.Header>
				<Empty.Media
					><CircleCheckIcon class="size-10 text-success" aria-hidden="true" /></Empty.Media
				>
				<Empty.Description>{m().auth.verified}</Empty.Description>
			</Empty.Header>
			<Empty.Content>
				<Button href={user ? '/account' : '/sign-in'}
					>{user ? m().nav.account : m().auth.signIn}</Button
				>
			</Empty.Content>
		{:else}
			<Empty.Header>
				{#if status === 'failed'}
					<Empty.Media><CircleXIcon class="size-10 text-danger" aria-hidden="true" /></Empty.Media>
					<Empty.Description role="alert">{m().auth.verifyFailed}</Empty.Description>
				{:else}
					<Empty.Media><MailIcon class="size-10 text-primary" aria-hidden="true" /></Empty.Media>
					<Empty.Description>{m().auth.verifyBanner}</Empty.Description>
				{/if}
			</Empty.Header>
			{#if user && !user.email_verified}
				<Empty.Content>
					<Button onclick={resend} disabled={resending}
						>{#if resending}<Spinner data-icon="inline-start" />{/if}{m().auth.resend}</Button
					>
				</Empty.Content>
			{:else if !user}
				<Empty.Content>
					<Button href="/sign-in?next=/verify-email">{m().auth.signIn}</Button>
				</Empty.Content>
			{/if}
		{/if}
	</Empty.Root>
</AuthCard>
