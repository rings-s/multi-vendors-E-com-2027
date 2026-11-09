<script lang="ts">
	import { invalidate } from '$app/navigation';
	import LifeBuoyIcon from '@lucide/svelte/icons/life-buoy';
	import { api, call } from '#lib/api/client.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const form = new FormState();
	let subject = $state('');
	let body = $state('');

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		if (subject.trim().length < 3) form.fail('subject', m().errors.fixFields);
		if (body.trim().length < 10) form.fail('body', m().ui.minChars({ n: 10 }));
		if (form.hasErrors) return;
		const res = await form.submit(
			() => call(api.POST('/api/v1/support/tickets', { body: { subject, body } })),
			{ success: m().account.ticketSent }
		);
		if (res.ok) {
			subject = '';
			body = '';
			await invalidate('app:tickets');
		}
	}
</script>

<svelte:head><title>{m().account.support} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={m().account.support} />
	<form onsubmit={submit} novalidate class="max-w-2xl">
		<Card.Root class="h-full">
			<Card.Header>
				<Card.Title role="heading" aria-level={2}>{m().account.newTicket}</Card.Title>
			</Card.Header>
			<Card.Content>
				<Field.Group>
					<FormField label={m().account.subject} id="t-subject" error={form.errors.subject}>
						{#snippet children({ id, invalid })}<Input
								{id}
								bind:value={subject}
								maxlength={200}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
					<FormField label={m().account.message} id="t-body" error={form.errors.body}>
						{#snippet children({ id, invalid })}<Textarea
								{id}
								bind:value={body}
								rows={5}
								maxlength={5000}
								aria-invalid={invalid || undefined}
							/>{/snippet}
					</FormField>
				</Field.Group>
			</Card.Content>
			<Card.Footer>
				<Button type="submit" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().common.submit}</Button
				>
			</Card.Footer>
		</Card.Root>
	</form>

	{#if data.tickets.items.length}
		<ul class="flex flex-col gap-3">
			{#each data.tickets.items as t (t.id)}
				<li>
					<Card.Root class="h-full">
						<Card.Content class="flex flex-col gap-3">
							<div class="flex flex-wrap items-center justify-between gap-2">
								<Card.Title><bdi>{t.subject}</bdi></Card.Title>
								<div class="flex items-center gap-2 text-xs text-ink-3">
									<StatusBadge status={t.status} />{fmt.date(t.created_at)}
								</div>
							</div>
							<p class="text-sm whitespace-pre-line text-ink-2"><bdi>{t.body}</bdi></p>
							{#if t.admin_response}
								<Alert.Root variant="info" role="note">
									<Alert.Title>{m().account.response}</Alert.Title>
									<Alert.Description class="whitespace-pre-line"
										>{t.admin_response}</Alert.Description
									>
								</Alert.Root>
							{/if}
						</Card.Content>
					</Card.Root>
				</li>
			{/each}
		</ul>
		<Paginator
			total={data.tickets.total}
			page={data.tickets.page}
			pageSize={data.tickets.page_size}
		/>
	{:else}
		<EmptyState icon={LifeBuoyIcon} title={m().account.noTickets} />
	{/if}
</div>
