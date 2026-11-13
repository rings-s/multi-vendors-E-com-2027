<script lang="ts" module>
	import { tv, type VariantProps } from 'tailwind-variants';

	export const tabsListVariants = tv({
		base: 'group/tabs-list inline-flex w-fit max-w-full items-center text-muted-foreground group-data-vertical/tabs:h-fit group-data-vertical/tabs:flex-col',
		variants: {
			variant: {
				// Segmented: a muted track with a raised marker that slides to the chosen tab.
				default: 'gap-0.5 rounded-lg bg-muted p-0.5 group-data-horizontal/tabs:h-10',
				// Line: tabs on a hairline; a 2px rule slides under the chosen tab.
				line: 'gap-5 overflow-x-auto border-b border-border group-data-horizontal/tabs:h-11 [scrollbar-width:none] [--ind-bg:var(--primary)]'
			}
		},
		defaultVariants: {
			variant: 'default'
		}
	});

	export type TabsListVariant = VariantProps<typeof tabsListVariants>['variant'];
</script>

<script lang="ts">
	import { Tabs as TabsPrimitive } from 'bits-ui';
	import { trackIndicator } from '#lib/indicator.js';
	import { cn } from '#lib/utils.js';

	let {
		ref = $bindable(null),
		variant = 'default',
		class: className,
		...restProps
	}: TabsPrimitive.ListProps & {
		variant?: TabsListVariant;
	} = $props();

	$effect(() => {
		if (ref) return trackIndicator(ref);
	});
</script>

<TabsPrimitive.List
	bind:ref
	data-slot="tabs-list"
	data-variant={variant}
	data-indicator={variant === 'line' ? 'line' : 'pill'}
	class={cn(tabsListVariants({ variant }), className)}
	{...restProps}
/>
