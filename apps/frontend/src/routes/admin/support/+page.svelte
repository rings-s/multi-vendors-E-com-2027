<script lang="ts">
	import { invalidate } from '$app/navigation';
	import LifeBuoyIcon from '@lucide/svelte/icons/life-buoy';
	import { api, call } from '#lib/api/client.js';
	import type { AdminTicket } from '#lib/api/types.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import QueryFilter from '#lib/components/app/QueryFilter.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	type TicketStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';
	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	let current = $state<AdminTicket | null>(null);
	let status = $state<TicketStatus>('IN_PROGRESS');
	let response = $state('');
	const form = new FormState();

	function open(ticket: AdminTicket) {
		current = ticket;
		status = ticket.status as TicketStatus;
		response = ticket.admin_response ?? '';
		form.reset();
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!current) return;
		const id = current.id;
		const res = await form.submit(
			() =>
				call(
					api.PATCH('/api/v1/admin/support-tickets/{ticket_id}', {
						params: { path: { ticket_id: id } },
						body: { status, admin_response: response || null }
					})
				),
			{ success: t.ticketUpdated }
		);
		if (res.ok) {
			current = null;
			await invalidate('app:admin-tickets');
		}
	}
</script>

<svelte:head><title>{t.support} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.support} />
	<QueryFilter
		param="status"
		value={data.status ?? ''}
		label={m().common.filters}
		options={['', 'OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'].map((s) => ({
			value: s,
			label: s ? statusLabel(s) : m().common.all
		}))}
	/>
	{#if data.tickets.items.length}
		<ul class="flex flex-col gap-3">
			{#each data.tickets.items as tk (tk.id)}
				<li>
					<Card.Root class="h-full">
						<Card.Content class="flex flex-col gap-2">
							<div class="flex flex-wrap items-center justify-between gap-2">
								<Card.Title><bdi>{tk.subject}</bdi></Card.Title>
								<div class="flex items-center gap-2">
									<StatusBadge status={tk.status} /><span class="text-xs text-ink-3"
										>{fmt.datetime(tk.created_at)}</span
									><Button size="sm" variant="outline" onclick={() => open(tk)}>{t.respond}</Button>
								</div>
							</div>
							<p class="text-sm whitespace-pre-line text-ink-2"><bdi>{tk.body}</bdi></p>
							{#if tk.admin_response}
								<Alert.Root variant="info" role="note">
									<Alert.Title>{m().account.response}</Alert.Title>
									<Alert.Description class="whitespace-pre-line"
										>{tk.admin_response}</Alert.Description
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

<Dialog.Root open={!!current} onOpenChange={(o) => !o && (current = null)}>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={save}>
			<Dialog.Header><Dialog.Title><bdi>{current?.subject}</bdi></Dialog.Title></Dialog.Header>
			<Field.Group>
				<FormField label={m().common.status} id="tk-status">
					{#snippet children({ id })}<NativeSelect.Root {id} bind:value={status} class="w-full"
							>{#each ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'] as s (s)}<NativeSelect.Option
									value={s}>{statusLabel(s)}</NativeSelect.Option
								>{/each}</NativeSelect.Root
						>{/snippet}
				</FormField>
				<FormField label={m().account.response} id="tk-resp" optional
					>{#snippet children({ id })}<Textarea
							{id}
							rows={5}
							bind:value={response}
						/>{/snippet}</FormField
				>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (current = null)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().common.save}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
