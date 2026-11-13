<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '#lib/utils.js';

	interface Props {
		title: string;
		description?: string | null;
		eyebrow?: string;
		class?: string;
		actions?: Snippet;
		meta?: Snippet;
		size?: 'lg' | 'md';
	}

	let {
		title,
		description,
		eyebrow,
		class: className,
		actions,
		meta,
		size = 'md'
	}: Props = $props();
</script>

<header class={cn('flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between', className)}>
	<div class="flex min-w-0 flex-col gap-2">
		{#if eyebrow}
			<p class="type-label text-ink-3">{eyebrow}</p>
		{/if}
		<h1
			class={cn(
				'font-display text-ink',
				size === 'lg' ? 'type-headline sm:text-[2.5rem]' : 'type-headline'
			)}
		>
			<bdi>{title}</bdi>
		</h1>
		{#if description}
			<p class="max-w-2xl text-pretty text-ink-2"><bdi>{description}</bdi></p>
		{/if}
		{@render meta?.()}
	</div>
	{#if actions}
		<div class="flex shrink-0 flex-wrap items-center gap-2">{@render actions()}</div>
	{/if}
</header>
