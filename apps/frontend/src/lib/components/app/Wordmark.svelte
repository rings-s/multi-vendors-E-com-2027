<script lang="ts">
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';
	import Logo from './Logo.svelte';

	interface Props {
		size?: 'sm' | 'md' | 'xl';
		class?: string;
	}

	let { size = 'md', class: className }: Props = $props();
</script>

<!-- Brand mark in emerald, then the name in ink. -->
<span
	class={cn(
		'inline-flex items-center gap-[0.45em] leading-none font-semibold tracking-[-0.025em] whitespace-nowrap text-ink',
		size === 'sm' && 'text-[1.0625rem]',
		size === 'md' && 'text-xl',
		size === 'xl' && 'text-4xl sm:text-5xl',
		className
	)}
>
	<Logo class="size-[1.4em] text-primary" />
	<span>{m().brand.name}</span>
</span>
