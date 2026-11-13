<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import * as ToggleGroup from '#lib/components/ui/toggle-group/index.js';

	/**
	 * A single-choice filter kept in the URL query string (`?{param}=value`), so the
	 * filtered view is shareable. The empty value clears the parameter.
	 */
	interface Props {
		param: string;
		value: string;
		options: { value: string; label: string }[];
		label: string;
	}

	let { param, value, options, label }: Props = $props();

	function select(v: string) {
		// Ignore the "deselect" event a single ToggleGroup emits when the active item is pressed.
		if (v === undefined || (v === '' && !options.some((o) => o.value === ''))) return;
		const url = new URL(page.url.href);
		url.searchParams.delete('page');
		if (v) url.searchParams.set(param, v);
		else url.searchParams.delete(param);
		void goto(url, { reset: false });
	}
</script>

<ToggleGroup.Root
	type="single"
	variant="outline"
	size="sm"
	spacing={1}
	class="flex-wrap"
	aria-label={label}
	{value}
	onValueChange={select}
>
	{#each options as o (o.value)}
		<ToggleGroup.Item value={o.value} class="px-3">
			{o.label}
		</ToggleGroup.Item>
	{/each}
</ToggleGroup.Root>
