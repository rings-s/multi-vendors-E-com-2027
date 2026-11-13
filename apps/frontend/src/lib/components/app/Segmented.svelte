<script lang="ts" generics="T extends string">
	import type { Component } from 'svelte';
	import { trackIndicator } from '#lib/indicator.js';
	import { dir } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	/**
	 * Segmented toggle: every choice stays visible and a raised marker slides to the chosen one.
	 * A radio group, so arrow keys move the choice and Tab enters and leaves it once.
	 */
	interface Option {
		value: T;
		label: string;
		icon?: Component;
		/** Language of the label when it differs from the page (e.g. the other locale's name). */
		lang?: string;
		testid?: string;
	}
	interface Props {
		value: T;
		options: Option[];
		/** Accessible name of the group. */
		label: string;
		onchange: (value: T) => void;
		/** Show icons only; labels become accessible names and tooltips. */
		iconOnly?: boolean;
		size?: 'sm' | 'md';
		/** Stretch segments to share the full width. */
		fill?: boolean;
		class?: string;
	}

	let {
		value,
		options,
		label,
		onchange,
		iconOnly = false,
		size = 'sm',
		fill = false,
		class: className
	}: Props = $props();

	function onkeydown(e: KeyboardEvent) {
		const forward = dir() === 'rtl' ? 'ArrowLeft' : 'ArrowRight';
		const back = dir() === 'rtl' ? 'ArrowRight' : 'ArrowLeft';
		const step =
			e.key === forward || e.key === 'ArrowDown'
				? 1
				: e.key === back || e.key === 'ArrowUp'
					? -1
					: 0;
		if (!step) return;
		e.preventDefault();
		const i = options.findIndex((o) => o.value === value);
		const next = options[(i + step + options.length) % options.length];
		onchange(next.value);
		const buttons = (e.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('[role=radio]');
		buttons[options.indexOf(next)]?.focus();
	}
</script>

<div
	role="radiogroup"
	aria-label={label}
	data-indicator="pill"
	tabindex="-1"
	{onkeydown}
	{@attach (node) => trackIndicator(node)}
	class={cn(
		'inline-flex shrink-0 items-center gap-0.5 rounded-lg bg-muted p-0.5 [--ind-radius:7px]',
		size === 'md' ? 'h-10' : 'h-9',
		fill && 'flex w-full',
		className
	)}
>
	{#each options as o (o.value)}
		<button
			type="button"
			role="radio"
			aria-checked={o.value === value}
			aria-label={iconOnly ? o.label : undefined}
			title={iconOnly ? o.label : undefined}
			tabindex={o.value === value ? 0 : -1}
			lang={o.lang}
			data-testid={o.testid}
			onclick={() => o.value !== value && onchange(o.value)}
			class={cn(
				'inline-flex h-full min-w-8 items-center justify-center gap-1.5 rounded-[7px] text-[0.8125rem] font-medium whitespace-nowrap text-ink-2 transition-colors duration-150 outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-ring/60 aria-checked:text-ink',
				iconOnly ? 'px-2' : 'px-3',
				fill && 'flex-1'
			)}
		>
			{#if o.icon}<o.icon class="size-4 shrink-0" aria-hidden="true" />{/if}
			{#if !iconOnly}<span>{o.label}</span>{/if}
		</button>
	{/each}
</div>
