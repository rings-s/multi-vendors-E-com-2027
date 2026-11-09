<script lang="ts">
	import StarIcon from '@lucide/svelte/icons/star';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		rating: number;
		count?: number;
		class?: string;
		compact?: boolean;
	}

	let { rating, count, class: className, compact = false }: Props = $props();
	const label = $derived(m().ui.ratingLabel({ rating: rating.toFixed(1) }));
</script>

{#if count === 0}
	<span class={cn('type-label text-ink-3', className)}>{m().stores.noReviews}</span>
{:else}
	<span class={cn('inline-flex items-center gap-1 type-label text-ink tabular', className)}>
		<span class="sr-only">{label}</span>
		{#if compact}
			<StarIcon class="size-3.5 fill-rating text-rating" aria-hidden="true" />
		{:else}
			<span class="inline-flex" aria-hidden="true">
				{#each [1, 2, 3, 4, 5] as i (i)}
					<StarIcon
						class={cn(
							'size-3',
							i <= Math.round(rating) ? 'fill-rating text-rating' : 'text-line-strong'
						)}
					/>
				{/each}
			</span>
		{/if}
		<span aria-hidden="true">{fmt.number(Number(rating.toFixed(1)))}</span>
		{#if count != null}
			<span class="text-ink-3">({fmt.number(count)})</span>
		{/if}
	</span>
{/if}
