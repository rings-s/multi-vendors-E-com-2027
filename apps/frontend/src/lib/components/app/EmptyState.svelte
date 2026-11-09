<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		title: string;
		description?: string;
		icon?: Component;
		class?: string;
		children?: Snippet;
	}

	let { title, description, icon: Icon, class: className, children }: Props = $props();
</script>

<Empty.Root class={cn('border-0 bg-surface-2 py-16', className)}>
	<Empty.Header>
		{#if Icon}
			<Empty.Media variant="icon">
				<Icon />
			</Empty.Media>
		{/if}
		<Empty.Title role="heading" aria-level={2}>{title}</Empty.Title>
		{#if description}
			<Empty.Description>{description}</Empty.Description>
		{/if}
	</Empty.Header>
	{#if children}
		<Empty.Content>{@render children()}</Empty.Content>
	{/if}
</Empty.Root>
