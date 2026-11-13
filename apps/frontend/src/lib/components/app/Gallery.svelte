<script lang="ts">
	import type { Image } from '#lib/api/types.js';
	import * as ToggleGroup from '#lib/components/ui/toggle-group/index.js';
	import Picture from './Picture.svelte';

	let { images, title }: { images: Image[]; title: string } = $props();
	let index = $state(0);
	const current = $derived(images[index] ?? images[0]);
</script>

<div class="flex flex-col gap-3">
	<div
		class="aspect-square overflow-hidden rounded-2xl bg-surface-2 ring-1 ring-edge"
		data-product-media
		style="view-transition-name: product-media"
	>
		<Picture src={current?.url} alt={current?.alt || title} fallback={title} loading="eager" />
	</div>
	{#if images.length > 1}
		<ToggleGroup.Root
			type="single"
			variant="outline"
			spacing={2}
			class="grid w-full grid-cols-5"
			aria-label={title}
			bind:value={() => String(index), (v) => v && (index = Number(v))}
		>
			{#each images as img, i (img.id)}
				<ToggleGroup.Item
					value={String(i)}
					aria-label="{title} {i + 1}"
					class="aspect-square h-auto w-full overflow-hidden rounded-lg border-2 border-transparent bg-surface-2 p-0 opacity-70 transition-[opacity,border-color] duration-150 hover:opacity-100 data-[state=on]:border-primary data-[state=on]:opacity-100"
				>
					<img src={img.url} alt="" class="size-full object-cover" />
				</ToggleGroup.Item>
			{/each}
		</ToggleGroup.Root>
	{/if}
</div>
