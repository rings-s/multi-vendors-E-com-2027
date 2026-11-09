<script lang="ts">
	import { goto } from '$app/navigation';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import InfoIcon from '@lucide/svelte/icons/info';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import DeleteDialog from '#lib/components/app/data/DeleteDialog.svelte';
	import RecordForm from '#lib/components/app/data/RecordForm.svelte';
	import JsonDetails from '#lib/components/app/JsonDetails.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { dataUrl, fieldLabel, modelLabel, noteText } from '#lib/data-admin.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().data);
	const schema = $derived(data.schema);
	const row = $derived(data.row);
	const model = $derived(modelLabel(t, schema.key));
	let deleteOpen = $state(false);

	// Every relation pointing here, with its count (0 when nothing references this row yet).
	const related = $derived(
		schema.relations.map((rel) => ({
			...rel,
			count: row.related.find((r) => r.model === rel.model && r.field === rel.field)?.count ?? 0
		}))
	);
	const ON_DELETE: Record<string, 'destructive' | 'secondary' | 'warning'> = {
		CASCADE: 'destructive',
		'SET NULL': 'secondary'
	};
</script>

<svelte:head><title>{row.label} · {model} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={row.label} eyebrow={model}>
		{#snippet meta()}
			<p class="text-sm text-ink-3"><code dir="ltr">{schema.key} · {row.pk}</code></p>
		{/snippet}
		{#snippet actions()}
			<Button variant="ghost" href={dataUrl(schema.key)}
				><ArrowLeftIcon data-icon="inline-start" class="rtl:rotate-180" />{model}</Button
			>
		{/snippet}
	</PageHeader>

	{#each schema.notes as note (note)}
		<Alert.Root variant={note === 'financial' ? 'warning' : 'default'}>
			<InfoIcon />
			<Alert.Description>{noteText(t, note)}</Alert.Description>
		</Alert.Root>
	{/each}

	<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
		<div class="min-w-0">
			{#key row.pk}
				<RecordForm {schema} {row} ondelete={() => (deleteOpen = true)} />
			{/key}
		</div>

		<aside class="flex min-w-0 flex-col gap-6">
			<section class="rounded-2xl border border-line bg-surface" aria-labelledby="related-title">
				<h2 id="related-title" class="border-b border-line px-4 py-3 type-label">{t.related}</h2>
				{#if related.length === 0}
					<p class="p-4 text-sm text-ink-3">{t.noRelated}</p>
				{:else}
					<ul class="divide-y divide-line">
						{#each related as rel (rel.model + rel.field)}
							<li class="flex items-center gap-2 px-4 py-2 text-sm">
								<a
									href="{dataUrl(rel.model)}?{rel.field}={encodeURIComponent(row.pk)}"
									class="min-w-0 flex-1 truncate hover:text-primary"
								>
									{modelLabel(t, rel.model)}
									<span class="text-xs text-ink-3">({fieldLabel(t, rel.field)})</span>
								</a>
								<Badge
									variant={rel.count ? (ON_DELETE[rel.on_delete] ?? 'outline') : 'outline'}
									title="ON DELETE {rel.on_delete}">{fmt.number(rel.count)}</Badge
								>
								<Button
									size="icon-sm"
									variant="ghost"
									aria-label="{t.add}: {modelLabel(t, rel.model)}"
									onclick={() =>
										goto(`${dataUrl(rel.model)}/new?${rel.field}=${encodeURIComponent(row.pk)}`)}
									><PlusIcon /></Button
								>
							</li>
						{/each}
					</ul>
				{/if}
			</section>

			{#if data.history}
				<section class="rounded-2xl border border-line bg-surface" aria-labelledby="history-title">
					<h2 id="history-title" class="border-b border-line px-4 py-3 type-label">{t.history}</h2>
					{#if data.history.items.length === 0}
						<p class="p-4 text-sm text-ink-3">{t.noHistory}</p>
					{:else}
						<ol class="divide-y divide-line">
							{#each data.history.items as entry (entry.id)}
								<li class="grid gap-1 px-4 py-3 text-sm">
									<div class="flex items-center justify-between gap-2">
										<code class="text-xs" dir="ltr">{entry.action}</code>
										<time class="text-xs text-ink-3" datetime={entry.created_at}
											>{fmt.datetime(entry.created_at)}</time
										>
									</div>
									{#if entry.actor_user_id}
										<a
											class="text-xs text-primary hover:underline"
											href={dataUrl('users', entry.actor_user_id)}>{m().admin.actor}</a
										>
									{/if}
									{#if entry.before || entry.after}
										<JsonDetails
											label={m().common.details}
											values={[entry.before, entry.after].filter(Boolean)}
										/>
									{/if}
								</li>
							{/each}
						</ol>
					{/if}
				</section>
			{/if}
		</aside>
	</div>
</div>

<DeleteDialog
	bind:open={deleteOpen}
	model={schema.key}
	pks={[row.pk]}
	ondeleted={() => goto(dataUrl(schema.key))}
/>
