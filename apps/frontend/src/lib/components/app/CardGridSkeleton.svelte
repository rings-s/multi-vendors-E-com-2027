<script lang="ts">
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	let { count = 8, aspect = 'aspect-[4/5]' }: { count?: number; aspect?: string } = $props();
</script>

<div
	class="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3 lg:grid-cols-4"
	role="status"
	aria-live="polite"
>
	<span class="sr-only">{m().common.loading}</span>
	{#each { length: count }, i (i)}
		<div class="flex flex-col gap-3">
			<Skeleton class={cn('w-full rounded-xl', aspect)} />
			<Skeleton class="h-4 w-3/4" />
			<Skeleton class="h-3 w-1/3" />
		</div>
	{/each}
</div>
