<script lang="ts">
	import type { OrderItem } from '#lib/api/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';

	let { items }: { items: OrderItem[] } = $props();
</script>

<Table.Root>
	<Table.Header>
		<Table.Row>
			<Table.Head>{m().orders.items}</Table.Head>
			<Table.Head class="text-end">{m().orders.qty}</Table.Head>
			<Table.Head class="text-end">{m().orders.unitPrice}</Table.Head>
			<Table.Head class="text-end">{m().orders.lineTotal}</Table.Head>
		</Table.Row>
	</Table.Header>
	<Table.Body>
		{#each items as item (item.id)}
			<Table.Row>
				<Table.Cell class="max-w-72 whitespace-normal">
					<p class="font-medium"><bdi>{item.title}</bdi></p>
					{#if item.sku}<p class="text-xs text-ink-3" dir="ltr">{item.sku}</p>{/if}
				</Table.Cell>
				<Table.Cell class="text-end tabular">{fmt.number(item.quantity)}</Table.Cell>
				<Table.Cell class="text-end tabular"
					>{fmt.money(item.unit_price - item.unit_discount)}</Table.Cell
				>
				<Table.Cell class="text-end tabular">{fmt.money(item.line_total)}</Table.Cell>
			</Table.Row>
		{/each}
	</Table.Body>
</Table.Root>
