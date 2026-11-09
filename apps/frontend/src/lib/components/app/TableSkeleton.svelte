<script lang="ts">
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	let { rows = 6, cols = 5 }: { rows?: number; cols?: number } = $props();
</script>

<div
	class="overflow-hidden rounded-2xl border border-line bg-surface"
	role="status"
	aria-live="polite"
>
	<span class="sr-only">{m().common.loading}</span>
	<Table.Root aria-hidden="true">
		<Table.Header>
			<Table.Row>
				{#each { length: cols }, c (c)}
					<Table.Head><Skeleton class="h-3 w-full" /></Table.Head>
				{/each}
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each { length: rows }, r (r)}
				<Table.Row>
					{#each { length: cols }, c (c)}
						<Table.Cell><Skeleton class={cn('h-4 w-full', c === 0 && 'max-w-40')} /></Table.Cell>
					{/each}
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
