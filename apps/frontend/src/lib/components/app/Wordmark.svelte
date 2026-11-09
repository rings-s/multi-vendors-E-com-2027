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

<!-- Logo mark, then the brand name in compressed semibold closed by the single violet dot. -->
<span
	class={cn(
		'inline-flex items-center gap-[0.4em] font-display leading-none whitespace-nowrap text-ink',
		size === 'sm' && 'text-lg',
		size === 'md' && 'text-[1.375rem]',
		size === 'xl' && 'text-5xl sm:text-7xl',
		className
	)}
>
	<Logo class="size-[1.2em]" />
	<span class="inline-flex items-baseline"
		>{m().brand.name}<span
			class={cn(
				'ms-[0.08em] inline-block shrink-0 rounded-full bg-primary',
				size === 'xl' ? 'size-[0.16em]' : 'size-[0.22em]'
			)}
			aria-hidden="true"
		></span></span
	>
</span>
