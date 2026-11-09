<script lang="ts">
	import { goto, invalidate } from '$app/navigation';
	import MonitorSmartphoneIcon from '@lucide/svelte/icons/monitor-smartphone';
	import { api, call } from '#lib/api/client.js';
	import { cart } from '#lib/cart.svelte.js';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const form = new FormState();
	let current = $state('');
	let next = $state('');

	async function changePassword(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		if (next.length < 10) return form.fail('new_password', m().auth.passwordHint);
		const res = await form.submit(
			() =>
				call(
					api.POST('/api/v1/users/me/password', {
						body: { current_password: current, new_password: next }
					})
				),
			{ success: m().account.passwordChanged }
		);
		if (res.ok) {
			current = '';
			next = '';
			await invalidate('app:sessions');
		}
	}

	async function revoke(id: string) {
		await action(() =>
			call(
				api.DELETE('/api/v1/auth/sessions/{session_id}', { params: { path: { session_id: id } } })
			)
		);
		await invalidate('app:sessions');
	}

	async function signOutAll() {
		if (
			!(await confirm({
				title: m().account.signOutAllConfirm,
				destructive: true,
				confirmLabel: m().account.signOutAll
			}))
		)
			return;
		const ok = await action(() => call(api.POST('/api/v1/auth/logout-all')));
		if (ok) {
			cart.clear();
			await goto('/sign-in', { invalidateAll: true });
		}
	}
</script>

<svelte:head><title>{m().account.security} · {m().brand.name}</title></svelte:head>

<div class="flex max-w-2xl flex-col gap-8">
	<PageHeader title={m().account.security} />

	<form onsubmit={changePassword} novalidate>
		<Card.Root class="h-full">
			<Card.Header>
				<Card.Title role="heading" aria-level={2}>{m().account.changePassword}</Card.Title>
			</Card.Header>
			<Card.Content>
				<Field.Group>
					{#if form.message}<Alert.Root variant="destructive"
							><Alert.Description>{form.message}</Alert.Description></Alert.Root
						>{/if}
					<FormField
						label={m().account.currentPassword}
						id="s-current"
						error={form.errors.current_password}
					>
						{#snippet children({ id, invalid })}<Input
								{id}
								type="password"
								bind:value={current}
								autocomplete="current-password"
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField
						label={m().auth.newPassword}
						id="s-new"
						error={form.errors.new_password}
						hint={m().auth.passwordHint}
					>
						{#snippet children({ id, invalid, describedBy })}<Input
								{id}
								type="password"
								bind:value={next}
								autocomplete="new-password"
								aria-invalid={invalid || undefined}
								aria-describedby={describedBy}
							/>{/snippet}
					</FormField>
				</Field.Group>
			</Card.Content>
			<Card.Footer>
				<Button type="submit" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().account
						.changePassword}</Button
				>
			</Card.Footer>
		</Card.Root>
	</form>

	<Card.Root>
		<Card.Header>
			<Card.Title role="heading" aria-level={2}>{m().account.sessions}</Card.Title>
			<Card.Action>
				<Button variant="outline" size="sm" onclick={signOutAll}>{m().account.signOutAll}</Button>
			</Card.Action>
		</Card.Header>
		<Card.Content>
			<Item.Group class="gap-0">
				{#each data.sessions as s, i (s.id)}
					{#if i > 0}<Item.Separator class="my-0" />{/if}
					<Item.Root role="listitem" class="px-0">
						<Item.Media variant="icon"><MonitorSmartphoneIcon aria-hidden="true" /></Item.Media>
						<Item.Content class="min-w-0">
							<Item.Title class="truncate font-normal" dir="ltr"
								>{s.user_agent ?? m().common.unknown}</Item.Title
							>
							<Item.Description class="text-xs">
								{#if s.current}<span class="font-medium text-primary">{m().account.thisDevice}</span
									> ·
								{/if}
								{m().account.lastSeen}: {fmt.relative(s.last_seen_at ?? s.created_at)}
								{#if s.ip_address}· <span dir="ltr">{s.ip_address}</span>{/if}
							</Item.Description>
						</Item.Content>
						{#if !s.current}
							<Item.Actions>
								<Button size="sm" variant="ghost" onclick={() => revoke(s.id)}
									>{m().account.revoke}</Button
								>
							</Item.Actions>
						{/if}
					</Item.Root>
				{/each}
			</Item.Group>
		</Card.Content>
	</Card.Root>
</div>
