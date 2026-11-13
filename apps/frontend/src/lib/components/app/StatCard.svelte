<script lang="ts">
	import MinusIcon from '@lucide/svelte/icons/minus';
	import TrendingDownIcon from '@lucide/svelte/icons/trending-down';
	import TrendingUpIcon from '@lucide/svelte/icons/trending-up';
	import type { Component } from 'svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		label: string;
		value: string;
		hint?: string;
		icon?: Component;
		tone?: 'default' | 'brand' | 'danger';
		/**
		 * Change against a comparison period. `sentiment` says whether the change is good
		 * news (a rising refund rate is not); the arrow and text carry it, not color alone.
		 */
		delta?: {
			text: string;
			direction: 'up' | 'down' | 'flat';
			sentiment: 'good' | 'bad' | 'neutral';
		};
		class?: string;
	}

	let {
		label,
		value,
		hint,
		icon: Icon,
		tone = 'default',
		delta,
		class: className
	}: Props = $props();

	const DeltaIcon = $derived(
		delta?.direction === 'up'
			? TrendingUpIcon
			: delta?.direction === 'down'
				? TrendingDownIcon
				: MinusIcon
	);
</script>

<Card.Root
	size="sm"
	data-tone={tone}
	class={cn(
		'justify-between data-[tone=brand]:bg-primary data-[tone=brand]:text-primary-foreground data-[tone=brand]:ring-transparent',
		className
	)}
>
	<Card.Header>
		<Card.Description class="group-data-[tone=brand]/card:text-primary-foreground/80"
			>{label}</Card.Description
		>
		{#if Icon}
			<Card.Action>
				<Icon
					class="size-4 text-ink-3 group-data-[tone=brand]/card:text-primary-foreground/70"
					aria-hidden="true"
				/>
			</Card.Action>
		{/if}
	</Card.Header>
	<Card.Content class="flex flex-col gap-1">
		<p
			class={cn(
				'text-[1.625rem] leading-tight font-semibold tracking-[-0.02em] tabular',
				tone === 'danger' && 'text-danger'
			)}
		>
			{value}
		</p>
		{#if delta}
			<p
				class={cn(
					'flex items-center gap-1 text-xs text-ink-3',
					delta.sentiment === 'good' && 'text-success',
					delta.sentiment === 'bad' && 'text-danger'
				)}
			>
				<DeltaIcon class="size-3.5 shrink-0" aria-hidden="true" />
				<span>{delta.text}</span>
			</p>
		{/if}
		{#if hint}
			<p class="text-xs text-ink-3 group-data-[tone=brand]/card:text-primary-foreground/70">
				<bdi>{hint}</bdi>
			</p>
		{/if}
	</Card.Content>
</Card.Root>
