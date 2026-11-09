<script lang="ts">
	import { m } from '#lib/i18n/state.svelte.js';
	import { Pagination as PaginationPrimitive } from 'bits-ui';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import { buttonVariants } from '#lib/components/ui/button/index.js';
	import { cn } from '#lib/utils.js';

	let {
		ref = $bindable(null),
		class: className,
		label: labelProp,
		...restProps
	}: PaginationPrimitive.NextButtonProps & { label?: string } = $props();
	const label = $derived(labelProp ?? m().common.next);
</script>

<PaginationPrimitive.NextButton
	bind:ref
	aria-label={label}
	class={cn(buttonVariants({ variant: 'ghost', size: 'default' }), 'pe-1.5!', className)}
	{...restProps}
>
	<span class="hidden sm:block">{label}</span>
	<ChevronRightIcon data-icon="inline-end" class="cn-rtl-flip" />
</PaginationPrimitive.NextButton>
