<script lang="ts">
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn, type WithElementRef } from '#lib/utils.js';
	import { useSidebar } from './context.svelte.js';
	import type { HTMLAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		class: className,
		children,
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLButtonElement>, HTMLButtonElement> = $props();

	const sidebar = useSidebar();
</script>

<button
	bind:this={ref}
	data-sidebar="rail"
	data-slot="sidebar-rail"
	aria-label={m().ui.toggleSidebar}
	tabindex={-1}
	onclick={sidebar.toggle}
	title={m().ui.toggleSidebar}
	class={cn(
		'absolute inset-y-0 z-20 hidden w-4 transition-all ease-linear group-data-[side=left]:-end-4 group-data-[side=right]:start-0 after:absolute after:inset-y-0 after:start-1/2 after:w-[2px] hover:after:bg-sidebar-border sm:flex ltr:-translate-x-1/2 rtl:translate-x-1/2',
		'in-data-[side=left]:cursor-w-resize in-data-[side=right]:cursor-e-resize',
		'[[data-side=left][data-state=collapsed]_&]:cursor-e-resize [[data-side=right][data-state=collapsed]_&]:cursor-w-resize',
		'group-data-[collapsible=offcanvas]:translate-x-0 group-data-[collapsible=offcanvas]:after:start-full hover:group-data-[collapsible=offcanvas]:bg-sidebar',
		'[[data-side=left][data-collapsible=offcanvas]_&]:-end-2',
		'[[data-side=right][data-collapsible=offcanvas]_&]:-start-2',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</button>
