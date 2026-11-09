<script lang="ts">
	import { m } from '#lib/i18n/state.svelte.js';
	import { Pagination as PaginationPrimitive } from 'bits-ui';
	import ChevronLeftIcon from '@lucide/svelte/icons/chevron-left';
	import { buttonVariants } from '#lib/components/ui/button/index.js';
	import { cn } from '#lib/utils.js';

	let {
		ref = $bindable(null),
		class: className,
		label: labelProp,
		...restProps
	}: PaginationPrimitive.PrevButtonProps & { label?: string } = $props();
	const label = $derived(labelProp ?? m().common.previous);
</script>

<PaginationPrimitive.PrevButton
	bind:ref
	aria-label={label}
	class={cn(buttonVariants({ variant: 'ghost', size: 'default' }), 'ps-1.5!', className)}
	{...restProps}
>
	<ChevronLeftIcon data-icon="inline-start" class="cn-rtl-flip" />
	<span class="hidden sm:block">{label}</span>
</PaginationPrimitive.PrevButton>
