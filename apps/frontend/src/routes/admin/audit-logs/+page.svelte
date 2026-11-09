<script lang="ts">
	import FileClockIcon from '@lucide/svelte/icons/file-clock';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import JsonDetails from '#lib/components/app/JsonDetails.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().admin);
</script>

<svelte:head><title>{t.auditLogs} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.auditLogs} />
	<FilterBar>
		<Field.Field class="w-52">
			<Field.Label for="al-a">{t.action}</Field.Label><Input
				id="al-a"
				name="action"
				dir="ltr"
				value={data.filters.action}
			/>
		</Field.Field>
		<Field.Field class="w-44">
			<Field.Label for="al-t">{t.entity}</Field.Label><Input
				id="al-t"
				name="entity_type"
				dir="ltr"
				value={data.filters.entity_type}
			/>
		</Field.Field>
		<Field.Field class="w-72">
			<Field.Label for="al-i">ID</Field.Label><Input
				id="al-i"
				name="entity_id"
				dir="ltr"
				value={data.filters.entity_id}
			/>
		</Field.Field>
	</FilterBar>
	{#if data.logs.items.length}
		<Item.Group class="gap-0 overflow-hidden rounded-2xl border border-line bg-surface">
			{#each data.logs.items as l, i (l.id)}
				{#if i > 0}<Item.Separator class="my-0" />{/if}
				<Item.Root role="listitem" class="rounded-none p-4">
					<Item.Content class="min-w-0">
						<Item.Title dir="ltr">
							{l.action}
							<span class="font-normal text-ink-3"
								>· {l.entity_type}{#if l.entity_id}
									{l.entity_id.slice(0, 8)}{/if}</span
							>
						</Item.Title>
						{#if l.before || l.after}
							<JsonDetails label="{t.before} / {t.after}" values={[l.before, l.after]} />
						{/if}
					</Item.Content>
					<Item.Actions class="self-start">
						<p class="text-xs text-ink-3">
							{fmt.datetime(l.created_at)}{#if l.ip_address}
								· <span dir="ltr">{l.ip_address}</span>{/if}{#if l.actor_user_id}
								· {t.actor} <span dir="ltr">{l.actor_user_id.slice(0, 8)}</span>{/if}
						</p>
					</Item.Actions>
				</Item.Root>
			{/each}
		</Item.Group>
		<Paginator total={data.logs.total} page={data.logs.page} pageSize={data.logs.page_size} />
	{:else}
		<EmptyState icon={FileClockIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>
