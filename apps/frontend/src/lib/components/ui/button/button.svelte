<script lang="ts" module>
	import { type VariantProps, tv } from 'tailwind-variants';
	import { cn, type WithElementRef } from '#lib/utils.js';
	import type { HTMLAnchorAttributes, HTMLButtonAttributes } from 'svelte/elements';

	export const buttonVariants = tv({
		base: "focus-visible:border-ring focus-visible:ring-ring/30 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 rounded-full border border-transparent bg-clip-padding text-sm font-medium tracking-[-0.014em] focus-visible:ring-4 aria-invalid:ring-3 active:not-aria-[haspopup]:scale-[0.98] [&_svg:not([class*='size-'])]:size-4 group/button inline-flex shrink-0 items-center justify-center whitespace-nowrap transition-[background-color,box-shadow,color,transform] duration-200 ease-out outline-none select-none disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:shrink-0",
		variants: {
			variant: {
				// The one saturated action; its elevation is tinted with the brand violet.
				default:
					'bg-primary text-primary-foreground hover:bg-primary-active hover:shadow-brand active:bg-primary-active',
				// White pill + hairline + soft lift (category pill / cookie button recipe).
				outline:
					'border-border bg-card text-foreground shadow-pill hover:bg-muted aria-expanded:bg-muted aria-expanded:text-foreground dark:border-input',
				secondary:
					'bg-secondary text-secondary-foreground hover:bg-surface-3 aria-expanded:bg-surface-3 aria-expanded:text-secondary-foreground',
				ghost:
					'text-foreground hover:bg-muted aria-expanded:bg-muted aria-expanded:text-foreground',
				destructive:
					'bg-destructive/10 hover:bg-destructive/15 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/20 text-destructive focus-visible:border-destructive/40 dark:hover:bg-destructive/30',
				link: 'text-foreground underline decoration-foreground/25 underline-offset-4 hover:decoration-foreground'
			},
			size: {
				default:
					'h-10 gap-2 px-4.5 has-data-[icon=inline-end]:pe-3.5 has-data-[icon=inline-start]:ps-3.5',
				xs: "h-7 gap-1 px-2.5 text-xs has-data-[icon=inline-end]:pe-2 has-data-[icon=inline-start]:ps-2 [&_svg:not([class*='size-'])]:size-3",
				sm: "h-8 gap-1.5 px-3.5 text-[0.8125rem] has-data-[icon=inline-end]:pe-2.5 has-data-[icon=inline-start]:ps-2.5 [&_svg:not([class*='size-'])]:size-3.5",
				lg: 'h-12 gap-2 px-6 text-base tracking-[-0.031em] has-data-[icon=inline-end]:pe-5 has-data-[icon=inline-start]:ps-5',
				icon: 'size-10',
				'icon-xs': "size-7 [&_svg:not([class*='size-'])]:size-3",
				'icon-sm': 'size-8',
				'icon-lg': "size-12 [&_svg:not([class*='size-'])]:size-5"
			}
		},
		defaultVariants: {
			variant: 'default',
			size: 'default'
		}
	});

	export type ButtonVariant = VariantProps<typeof buttonVariants>['variant'];
	export type ButtonSize = VariantProps<typeof buttonVariants>['size'];

	export type ButtonProps = WithElementRef<HTMLButtonAttributes> &
		WithElementRef<HTMLAnchorAttributes> & {
			variant?: ButtonVariant;
			size?: ButtonSize;
		};
</script>

<script lang="ts">
	let {
		class: className,
		variant = 'default',
		size = 'default',
		ref = $bindable(null),
		href = undefined,
		type = 'button',
		disabled,
		children,
		...restProps
	}: ButtonProps = $props();
</script>

{#if href}
	<a
		bind:this={ref}
		data-slot="button"
		class={cn(buttonVariants({ variant, size }), className)}
		href={disabled ? undefined : href}
		aria-disabled={disabled}
		role={disabled ? 'link' : undefined}
		tabindex={disabled ? -1 : undefined}
		{...restProps}
	>
		{@render children?.()}
	</a>
{:else}
	<button
		bind:this={ref}
		data-slot="button"
		class={cn(buttonVariants({ variant, size }), className)}
		{type}
		{disabled}
		{...restProps}
	>
		{@render children?.()}
	</button>
{/if}
