<script lang="ts">
	import type { Snippet } from 'svelte';
	import * as Card from '#lib/components/ui/card/index.js';

	interface Props {
		title: string;
		subtitle?: string;
		children: Snippet;
		footer?: Snippet;
	}

	let { title, subtitle, children, footer }: Props = $props();
</script>

<div class="container-page grid min-h-[calc(100dvh-4rem)] place-items-center py-12 sm:py-16">
	<div class="flex w-full max-w-md flex-col gap-8">
		<div class="flex flex-col gap-2 text-center">
			<h1 class="font-display type-headline text-ink">{title}</h1>
			{#if subtitle}<p class="text-ink-2">{subtitle}</p>{/if}
		</div>
		<Card.Root class="shadow-soft">
			<Card.Content>{@render children()}</Card.Content>
		</Card.Root>
		{#if footer}
			<div class="flex flex-col gap-2 text-center text-sm text-ink-2">{@render footer()}</div>
		{/if}
	</div>
</div>
