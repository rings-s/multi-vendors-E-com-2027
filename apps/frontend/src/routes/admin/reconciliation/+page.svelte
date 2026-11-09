<script lang="ts">
	import { invalidate } from '$app/navigation';
	import ScaleIcon from '@lucide/svelte/icons/scale';
	import { api, call } from '#lib/api/client.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import JsonDetails from '#lib/components/app/JsonDetails.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	const form = new FormState();
	let start = $state('');
	let end = $state('');
	let apply = $state(false);

	async function run(e: SubmitEvent) {
		e.preventDefault();
		if (
			apply &&
			!(await confirm({
				title: t.applyUpdates,
				description: t.runReconciliation,
				destructive: true
			}))
		)
			return;
		const res = await form.submit(
			() =>
				call(
					api.POST('/api/v1/admin/reconciliation', {
						body: {
							period_start: start ? new Date(start).toISOString() : null,
							period_end: end ? new Date(end).toISOString() : null,
							apply
						}
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) await invalidate('app:reconciliation');
	}
</script>

<svelte:head><title>{t.reconciliation} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={t.reconciliation} />
	<form onsubmit={run}>
		<Card.Root>
			<Card.Content>
				<Field.Group class="flex-row flex-wrap items-end gap-4">
					<FormField label={t.periodStart} id="rc-start" optional
						>{#snippet children({ id })}<Input
								{id}
								type="datetime-local"
								bind:value={start}
							/>{/snippet}</FormField
					>
					<FormField label={t.periodEnd} id="rc-end" optional
						>{#snippet children({ id })}<Input
								{id}
								type="datetime-local"
								bind:value={end}
							/>{/snippet}</FormField
					>
					<Field.Field orientation="horizontal" class="h-8 w-auto">
						<Checkbox id="rc-apply" bind:checked={apply} /><Field.Label
							for="rc-apply"
							class="font-normal">{t.applyUpdates}</Field.Label
						>
					</Field.Field>
					<Button type="submit" disabled={form.pending}
						>{#if form.pending}<Spinner
								data-icon="inline-start"
							/>{/if}{t.runReconciliation}</Button
					>
				</Field.Group>
			</Card.Content>
		</Card.Root>
	</form>
	{#if data.runs.items.length}
		<ul class="flex flex-col gap-3">
			{#each data.runs.items as r (r.id)}
				<li>
					<Card.Root class="h-full">
						<Card.Content class="flex flex-col gap-3">
							<div class="flex flex-wrap items-center justify-between gap-3">
								<div class="flex items-center gap-3">
									<StatusBadge status={r.status} /><span class="text-sm text-ink-3"
										>{fmt.datetime(r.created_at)} · {r.scope} · {r.provider}</span
									>
								</div>
								<div class="flex gap-4 text-sm tabular">
									<span>{t.checked}: {fmt.number(r.checked_count)}</span>
									<span class={cn(r.mismatch_count && 'text-destructive')}
										>{t.mismatches}: {fmt.number(r.mismatch_count)}</span
									>
									<span>{t.applied}: {fmt.number(r.applied_updates)}</span>
								</div>
							</div>
							{#if r.details.length}
								<JsonDetails label={m().common.details} values={[r.details]} />
							{/if}
						</Card.Content>
					</Card.Root>
				</li>
			{/each}
		</ul>
		<Paginator total={data.runs.total} page={data.runs.page} pageSize={data.runs.page_size} />
	{:else}
		<EmptyState icon={ScaleIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>
