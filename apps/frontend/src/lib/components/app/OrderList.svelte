<script lang="ts">
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import type { OrderListItem } from '#lib/api/types.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import StatusBadge from './StatusBadge.svelte';

	let { orders }: { orders: OrderListItem[] } = $props();
</script>

<Item.Group class="gap-0 overflow-hidden rounded-2xl border border-line bg-surface">
	{#each orders as o, i (o.id)}
		{#if i > 0}<Item.Separator class="my-0" />{/if}
		<Item.Root role="listitem" class="rounded-none p-4 sm:p-5">
			{#snippet child({ props })}
				<a href="/account/orders/{o.id}" {...props} data-testid="order-row">
					<Item.Content class="min-w-0">
						<Item.Title class="tabular" dir="ltr">{o.number}</Item.Title>
						<Item.Description class="truncate">
							{fmt.list(o.store_names)} · {fmt.date(o.created_at)}
						</Item.Description>
					</Item.Content>
					<Item.Actions class="gap-4">
						<StatusBadge status={o.status} />
						<p class="hidden w-28 text-end font-medium tabular sm:block">{fmt.money(o.total)}</p>
						<ChevronRightIcon class="rtl-flip size-4 text-ink-3" aria-hidden="true" />
						<span class="sr-only">{m().common.view}</span>
					</Item.Actions>
				</a>
			{/snippet}
		</Item.Root>
	{/each}
</Item.Group>
