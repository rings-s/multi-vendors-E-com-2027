<script lang="ts">
	import CheckIcon from '@lucide/svelte/icons/check';
	import XIcon from '@lucide/svelte/icons/x';
	import type { DataField } from '#lib/api/types.js';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import { dataUrl } from '#lib/data-admin.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';

	/** One value of a record, formatted by its column kind (list cells and read-only fields). */
	interface Props {
		field: DataField;
		value: unknown;
		/** Label of the referenced record, for foreign keys. */
		fkLabel?: string | null;
		/** Truncate long text (list view). */
		compact?: boolean;
	}

	let { field, value, fkLabel = null, compact = false }: Props = $props();

	const text = $derived(value == null ? '' : String(value));
</script>

{#if value == null || value === ''}
	<span class="text-ink-3">—</span>
{:else if field.kind === 'boolean'}
	{#if value}
		<CheckIcon class="size-4 text-success" aria-label={m().common.yes} />
	{:else}
		<XIcon class="size-4 text-ink-3" aria-label={m().common.no} />
	{/if}
{:else if field.fk}
	<a
		href={dataUrl(field.fk, text)}
		class="text-primary underline-offset-4 hover:underline"
		title={text}
		dir={fkLabel ? undefined : 'ltr'}>{fkLabel ?? text.slice(0, 8)}</a
	>
{:else if field.choices}
	<StatusBadge status={text} />
{:else if field.kind === 'money'}
	<span class="tabular" title="{text} halalas">{fmt.money(Number(value))}</span>
{:else if field.kind === 'integer' || field.kind === 'float' || field.kind === 'decimal'}
	<span class="tabular" dir="ltr">{text}</span>
{:else if field.kind === 'datetime'}
	<time datetime={text} class="whitespace-nowrap tabular">{fmt.datetime(text)}</time>
{:else if field.kind === 'json'}
	{#if compact}
		<code class="block max-w-64 truncate text-xs text-ink-2" dir="ltr">{JSON.stringify(value)}</code
		>
	{:else}
		<pre
			class="max-h-72 overflow-auto rounded-lg bg-surface-2 p-3 text-xs"
			dir="ltr">{JSON.stringify(value, null, 2)}</pre>
	{/if}
{:else if field.kind === 'uuid'}
	<code class="text-xs" dir="ltr" title={text}>{compact ? text.slice(0, 8) : text}</code>
{:else if compact}
	<span class="block max-w-72 truncate" title={text}>{text}</span>
{:else}
	<span class="whitespace-pre-wrap">{text}</span>
{/if}
