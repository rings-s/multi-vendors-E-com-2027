<script lang="ts">
	import StarIcon from '@lucide/svelte/icons/star';
	import * as ToggleGroup from '#lib/components/ui/toggle-group/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	let { value = $bindable(5), label }: { value?: number; label: string } = $props();
	let hover = $state<number | null>(null);
</script>

<ToggleGroup.Root
	type="single"
	size="lg"
	spacing={1}
	aria-label={label}
	bind:value={() => String(value), (v) => v && (value = Number(v))}
>
	{#each [1, 2, 3, 4, 5] as n (n)}
		<ToggleGroup.Item
			value={String(n)}
			aria-label={m().ui.ratingLabel({ rating: String(n) })}
			class="px-1 data-[state=on]:bg-transparent"
			onpointerenter={() => (hover = n)}
			onpointerleave={() => (hover = null)}
		>
			<!-- Rating stars are deliberately larger than the default toggle icon size. -->
			<StarIcon
				class={cn(
					'size-6 transition-colors',
					n <= (hover ?? value) ? 'fill-rating text-rating' : 'text-line-strong'
				)}
			/>
		</ToggleGroup.Item>
	{/each}
</ToggleGroup.Root>
