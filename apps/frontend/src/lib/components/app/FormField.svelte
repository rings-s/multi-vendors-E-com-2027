<script lang="ts">
	import type { Snippet } from 'svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		label: string;
		/** id of the control, used for `<label for>` and `aria-describedby`. */
		id: string;
		error?: string | null;
		hint?: string;
		optional?: boolean;
		class?: string;
		orientation?: 'vertical' | 'horizontal';
		children: Snippet<[{ id: string; invalid: boolean; describedBy: string | undefined }]>;
	}

	let {
		label,
		id,
		error,
		hint,
		optional,
		class: className,
		orientation = 'vertical',
		children
	}: Props = $props();

	const describedBy = $derived(
		[hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined
	);
</script>

<Field.Field {orientation} data-invalid={error ? true : undefined} class={cn(className)}>
	<Field.Label for={id}>
		{label}
		{#if optional}<span class="text-xs font-normal text-ink-3">({m().common.optional})</span>{/if}
	</Field.Label>
	{@render children({ id, invalid: !!error, describedBy })}
	{#if hint && !error}
		<Field.Description id="{id}-hint">{hint}</Field.Description>
	{/if}
	{#if error}
		<Field.Error id="{id}-error">{error}</Field.Error>
	{/if}
</Field.Field>
