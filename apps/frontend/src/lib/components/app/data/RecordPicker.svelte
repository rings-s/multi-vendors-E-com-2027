<script lang="ts">
	import CheckIcon from '@lucide/svelte/icons/check';
	import ChevronsUpDownIcon from '@lucide/svelte/icons/chevrons-up-down';
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import XIcon from '@lucide/svelte/icons/x';
	import { api, call } from '#lib/api/client.js';
	import type { DataLookupItem } from '#lib/api/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Popover from '#lib/components/ui/popover/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { dataUrl } from '#lib/data-admin.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	/**
	 * Foreign-key picker: searches the referenced table (`/admin/data/{model}/lookup`)
	 * and stores the selected record's primary key.
	 */
	interface Props {
		id: string;
		/** Referenced table. */
		model: string;
		value: string;
		/** Label of the current value, when known. */
		label?: string | null;
		nullable?: boolean;
		disabled?: boolean;
		invalid?: boolean;
		describedBy?: string;
		onchange?: (value: string, label: string | null) => void;
	}

	let {
		id,
		model,
		value = $bindable(),
		label = null,
		nullable = false,
		disabled = false,
		invalid = false,
		describedBy,
		onchange
	}: Props = $props();

	const t = $derived(m().data);
	let open = $state(false);
	let query = $state('');
	let items = $state<DataLookupItem[]>([]);
	let loading = $state(false);
	let picked = $state<string | null>(null);
	let seq = 0;
	let timer: ReturnType<typeof setTimeout> | undefined;

	const shown = $derived(picked ?? label ?? (value ? value.slice(0, 8) : ''));

	async function search(q: string) {
		const mine = ++seq;
		loading = true;
		try {
			const res = await call(
				api.GET('/api/v1/admin/data/{model}/lookup', {
					params: { path: { model }, query: q ? { q } : {} }
				})
			);
			if (mine === seq) items = res;
		} catch {
			if (mine === seq) items = [];
		} finally {
			if (mine === seq) loading = false;
		}
	}

	function onInput() {
		clearTimeout(timer);
		timer = setTimeout(() => search(query.trim()), 200);
	}

	function choose(item: DataLookupItem | null) {
		value = item?.pk ?? '';
		picked = item?.label ?? null;
		onchange?.(value, picked);
		open = false;
	}

	$effect(() => {
		if (open) {
			query = '';
			void search('');
		}
	});
</script>

<div class="flex min-w-0 items-center gap-1">
	<Popover.Root bind:open>
		<Popover.Trigger {disabled}>
			{#snippet child({ props })}
				<Button
					{...props}
					{id}
					variant="outline"
					role="combobox"
					aria-expanded={open}
					aria-invalid={invalid || undefined}
					aria-describedby={describedBy}
					class={cn('w-full min-w-0 justify-between font-normal', !value && 'text-ink-3')}
				>
					<span class="truncate">{value ? shown : t.pickRecord}</span>
					<ChevronsUpDownIcon data-icon="inline-end" class="opacity-50" />
				</Button>
			{/snippet}
		</Popover.Trigger>
		<Popover.Content class="w-80 p-2" align="start">
			<Input
				bind:value={query}
				oninput={onInput}
				placeholder={t.searchRecord}
				aria-label={t.searchRecord}
				class="mb-2"
			/>
			<div class="max-h-64 overflow-y-auto" role="listbox" aria-label={t.pickRecord}>
				{#if loading && items.length === 0}
					<div class="flex justify-center p-3"><Spinner /></div>
				{:else if items.length === 0}
					<p class="p-3 text-sm text-ink-3">{t.noMatch}</p>
				{:else}
					{#each items as item (item.pk)}
						<button
							type="button"
							role="option"
							aria-selected={item.pk === value}
							class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-start text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
							onclick={() => choose(item)}
						>
							<CheckIcon class={cn('size-4 shrink-0', item.pk !== value && 'invisible')} />
							<span class="min-w-0 flex-1 truncate"><bdi>{item.label}</bdi></span>
							<span class="shrink-0 font-mono text-xs text-ink-3" dir="ltr"
								>{item.pk.slice(0, 8)}</span
							>
						</button>
					{/each}
				{/if}
			</div>
		</Popover.Content>
	</Popover.Root>
	{#if value && nullable && !disabled}
		<Button
			size="icon-sm"
			variant="ghost"
			aria-label="{t.clear}: {shown}"
			onclick={() => choose(null)}><XIcon /></Button
		>
	{/if}
	{#if value}
		<Button
			size="icon-sm"
			variant="ghost"
			href={dataUrl(model, value)}
			aria-label="{t.open}: {shown}"><ExternalLinkIcon /></Button
		>
	{/if}
</div>
