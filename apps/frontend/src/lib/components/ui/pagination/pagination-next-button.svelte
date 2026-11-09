<script lang="ts">
	import { m } from '#lib/i18n/state.svelte.js';
	import { Pagination as PaginationPrimitive } from 'bits-ui';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import { cn } from '#lib/utils.js';
	import { buttonVariants } from '../button/index.js';

	let {
		ref = $bindable(null),
		class: className,
		children,
		...restProps
	}: PaginationPrimitive.NextButtonProps = $props();
</script>

{#snippet Fallback()}
	<span>{m().common.next}</span>
	<ChevronRightIcon class={cn('cn-rtl-flip size-4', className)} />
{/snippet}

<PaginationPrimitive.NextButton
	bind:ref
	aria-label={m().ui.nextPage}
	class={cn(buttonVariants({ variant: 'ghost' }), 'pe-1.5!', className)}
	{...restProps}
>
	{#if children}
		{@render children?.()}
	{:else}
		{@render Fallback()}
	{/if}
</PaginationPrimitive.NextButton>
