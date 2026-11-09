<script lang="ts">
	import { initials } from '#lib/format.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		src?: string | null;
		alt: string;
		/** Text used for the monogram when there is no image. */
		fallback?: string;
		class?: string;
		loading?: 'lazy' | 'eager';
	}

	let { src, alt, fallback, class: className, loading = 'lazy' }: Props = $props();
	let failed = $state(false);
	// A deterministic warm tint per item keeps placeholder grids from looking uniform.
	const hue = $derived(
		[...(fallback ?? alt)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7) % 360
	);
</script>

{#if src && !failed}
	<img
		{src}
		{alt}
		{loading}
		decoding="async"
		class={cn('size-full object-cover', className)}
		onerror={() => (failed = true)}
	/>
{:else}
	<div
		class={cn('[container-type:size] grid size-full place-items-center', className)}
		style="background: color-mix(in oklab, oklch(78% 0.025 {hue}) 18%, var(--surface-2));"
		role="img"
		aria-label={alt}
	>
		<span
			class="font-display text-[min(32cqmin,3rem)] leading-none text-ink/25 uppercase"
			aria-hidden="true"
		>
			{initials(fallback ?? alt)}
		</span>
	</div>
{/if}
