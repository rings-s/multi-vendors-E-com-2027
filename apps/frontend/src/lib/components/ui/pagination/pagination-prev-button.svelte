<script lang="ts">
	import { m } from '#lib/i18n/state.svelte.js';
	import { Pagination as PaginationPrimitive } from 'bits-ui';
	import ChevronLeftIcon from '@lucide/svelte/icons/chevron-left';
	import { cn } from '#lib/utils.js';
	import { buttonVariants } from '../button/index.js';

	let {
		ref = $bindable(null),
		class: className,
		children,
		...restProps
	}: PaginationPrimitive.PrevButtonProps = $props();
</script>

{#snippet Fallback()}
	<ChevronLeftIcon class={cn('cn-rtl-flip size-4', className)} />
	<span>{m().common.previous}</span>
{/snippet}

<PaginationPrimitive.PrevButton
	bind:ref
	aria-label={m().ui.previousPage}
	class={cn(buttonVariants({ variant: 'ghost' }), 'ps-1.5!', className)}
	{...restProps}
>
	{#if children}
		{@render children?.()}
	{:else}
		{@render Fallback()}
	{/if}
</PaginationPrimitive.PrevButton>
