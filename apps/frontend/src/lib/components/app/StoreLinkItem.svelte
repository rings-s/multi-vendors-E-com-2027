<script lang="ts">
	import * as Item from '#lib/components/ui/item/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import Picture from './Picture.svelte';
	import RatingStars from './RatingStars.svelte';

	interface Props {
		store: {
			slug: string;
			name: string;
			logo_url?: string | null;
			rating_avg: number;
			rating_count: number;
		};
	}

	let { store }: Props = $props();
</script>

<Item.Root variant="outline" class="rounded-2xl bg-surface p-4">
	{#snippet child({ props })}
		<a href="/stores/{store.slug}" {...props}>
			<Item.Media variant="image" class="size-12 rounded-xl bg-surface-2">
				<Picture src={store.logo_url} alt="" fallback={store.name} />
			</Item.Media>
			<Item.Content class="min-w-0">
				<Item.Description class="text-xs">{m().catalog.soldBy}</Item.Description>
				<Item.Title class="truncate"><bdi>{store.name}</bdi></Item.Title>
				<RatingStars rating={store.rating_avg} count={store.rating_count} compact />
			</Item.Content>
			<Item.Actions><span class="text-sm text-primary">{m().catalog.visitStore}</span></Item.Actions
			>
		</a>
	{/snippet}
</Item.Root>
