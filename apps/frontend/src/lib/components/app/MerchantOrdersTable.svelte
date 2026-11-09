<script lang="ts">
	import { goto } from '$app/navigation';
	import type { MerchantOrderMerchantView } from '#lib/api/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import StatusBadge from './StatusBadge.svelte';

	interface Props {
		orders: MerchantOrderMerchantView[];
		/** Detail URL for an order. */
		href: (o: MerchantOrderMerchantView) => string;
		showCommission?: boolean;
	}

	let { orders, href, showCommission = true }: Props = $props();
</script>

<div class="overflow-hidden rounded-2xl border border-line bg-surface">
	<Table.Root>
		<Table.Header>
			<Table.Row>
				<Table.Head>{m().orders.number}</Table.Head>
				<Table.Head>{m().merchant.customer}</Table.Head>
				<Table.Head>{m().common.date}</Table.Head>
				<Table.Head>{m().common.status}</Table.Head>
				<Table.Head class="text-end">{m().common.total}</Table.Head>
				{#if showCommission}<Table.Head class="text-end">{m().merchant.net}</Table.Head>{/if}
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each orders as o (o.id)}
				<Table.Row
					class="cursor-pointer"
					onclick={() => goto(href(o))}
					data-testid="merchant-order-row"
				>
					<Table.Cell
						><a
							href={href(o)}
							class="font-medium tabular hover:underline"
							dir="ltr"
							onclick={(e) => e.stopPropagation()}>{o.number}</a
						></Table.Cell
					>
					<Table.Cell><bdi>{o.customer_name}</bdi></Table.Cell>
					<Table.Cell class="text-ink-3 tabular">{fmt.datetime(o.created_at)}</Table.Cell>
					<Table.Cell>
						<div class="flex flex-wrap gap-1.5">
							<StatusBadge status={o.status} />
							{#if o.cancellation_status === 'REQUESTED'}<StatusBadge
									status="REQUESTED"
									label={m().admin.cancellationRequested}
								/>{/if}
						</div>
					</Table.Cell>
					<Table.Cell class="text-end tabular">{fmt.money(o.total)}</Table.Cell>
					{#if showCommission}<Table.Cell class="text-end font-medium tabular"
							>{fmt.money(o.merchant_net)}</Table.Cell
						>{/if}
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
