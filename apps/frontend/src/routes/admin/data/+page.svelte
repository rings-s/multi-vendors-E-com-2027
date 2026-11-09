<script lang="ts">
	import EyeIcon from '@lucide/svelte/icons/eye';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import SearchIcon from '@lucide/svelte/icons/search';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as InputGroup from '#lib/components/ui/input-group/index.js';
	import { dataUrl, groupLabel, modelLabel } from '#lib/data-admin.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().data);
	let filter = $state('');

	const groups = $derived.by(() => {
		const needle = filter.trim().toLowerCase();
		const out: Record<string, typeof data.models> = {};
		for (const model of data.models) {
			const label = modelLabel(t, model.key);
			if (
				needle &&
				!`${label} ${model.key} ${groupLabel(t, model.group)}`.toLowerCase().includes(needle)
			)
				continue;
			(out[model.group] ??= []).push(model);
		}
		return Object.entries(out)
			.map(([group, models]) => ({
				group,
				label: groupLabel(t, group),
				models: models.toSorted((a, b) => modelLabel(t, a.key).localeCompare(modelLabel(t, b.key)))
			}))
			.toSorted((a, b) => a.label.localeCompare(b.label));
	});
</script>

<svelte:head><title>{t.title} · {m().admin.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.title} description={t.description}>
		{#snippet actions()}
			<InputGroup.Root class="w-full sm:w-72">
				<InputGroup.Addon><SearchIcon /></InputGroup.Addon>
				<InputGroup.Input
					bind:value={filter}
					placeholder={t.searchModels}
					aria-label={t.searchModels}
					type="search"
				/>
			</InputGroup.Root>
		{/snippet}
	</PageHeader>

	{#if groups.length === 0}
		<EmptyState title={t.noModels} />
	{:else}
		<div class="grid gap-6 lg:grid-cols-2">
			{#each groups as g (g.group)}
				<section
					class="overflow-hidden rounded-2xl border border-line bg-surface"
					aria-labelledby="group-{g.group}"
				>
					<h2 id="group-{g.group}" class="border-b border-line bg-surface-2 px-4 py-3 type-label">
						{g.label}
					</h2>
					<ul class="divide-y divide-line">
						{#each g.models as model (model.key)}
							{@const writable = model.user_can_manage}
							<li class="flex items-center gap-3 px-4 py-2.5">
								<a href={dataUrl(model.key)} class="group min-w-0 flex-1">
									<span class="block font-medium text-ink group-hover:text-primary"
										>{modelLabel(t, model.key)}</span
									>
									<code class="block truncate text-xs text-ink-3" dir="ltr">{model.key}</code>
								</a>
								<div class="flex shrink-0 items-center gap-1">
									{#if writable && model.can_add}
										<Button size="sm" variant="ghost" href="{dataUrl(model.key)}/new"
											><PlusIcon data-icon="inline-start" />{t.add}</Button
										>
									{/if}
									<Button size="sm" variant="ghost" href={dataUrl(model.key)}>
										{#if writable && model.can_change}
											<PencilIcon data-icon="inline-start" />{t.change}
										{:else}
											<EyeIcon data-icon="inline-start" />{m().common.view}
										{/if}
									</Button>
								</div>
							</li>
						{/each}
					</ul>
				</section>
			{/each}
		</div>
	{/if}
</div>
