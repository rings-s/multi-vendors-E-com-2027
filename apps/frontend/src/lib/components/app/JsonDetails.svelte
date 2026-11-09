<script lang="ts">
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Collapsible from '#lib/components/ui/collapsible/index.js';
	import { ScrollArea } from '#lib/components/ui/scroll-area/index.js';
	import { cn } from '#lib/utils.js';

	/** A disclosure that reveals one or more JSON payloads (e.g. before/after snapshots). */
	interface Props {
		label: string;
		values: unknown[];
		class?: string;
	}

	let { label, values, class: className }: Props = $props();
</script>

<Collapsible.Root class={className}>
	<Collapsible.Trigger>
		{#snippet child({ props })}
			<Button {...props} variant="link" size="sm" class="group px-0"
				>{label}<ChevronDownIcon
					data-icon="inline-end"
					class="transition-transform group-data-[state=open]:rotate-180"
				/></Button
			>
		{/snippet}
	</Collapsible.Trigger>
	<Collapsible.Content>
		<div class={cn('mt-2 grid gap-2', values.length > 1 && 'md:grid-cols-2')} dir="ltr">
			{#each values as v, i (i)}
				<ScrollArea class="max-h-72 rounded-lg bg-surface-2">
					<pre class="p-3 text-xs">{JSON.stringify(v, null, 2)}</pre>
				</ScrollArea>
			{/each}
		</div>
	</Collapsible.Content>
</Collapsible.Root>
