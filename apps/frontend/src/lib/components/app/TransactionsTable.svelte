<script lang="ts">
	import type { RecentTransaction } from '#lib/api/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	let { items }: { items: RecentTransaction[] } = $props();
</script>

<div class="overflow-hidden rounded-2xl border border-line bg-surface">
	<Table.Root>
		<Table.Header>
			<Table.Row>
				<Table.Head>{m().common.date}</Table.Head>
				<Table.Head>{m().merchant.type}</Table.Head>
				<Table.Head>{m().merchant.description}</Table.Head>
				<Table.Head class="text-end">{m().common.amount}</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each items as t (t.id)}
				<Table.Row>
					<Table.Cell class="text-ink-3 tabular">{fmt.datetime(t.created_at)}</Table.Cell>
					<Table.Cell
						>{statusLabel(t.transaction_type)}{#if t.is_test}<Badge variant="warning" class="ms-1.5"
								>{m().common.testMode}</Badge
							>{/if}</Table.Cell
					>
					<Table.Cell class="max-w-80 truncate text-ink-2"><bdi>{t.description}</bdi></Table.Cell>
					<Table.Cell
						class={cn(
							'text-end font-medium tabular',
							t.direction === 'DEBIT' ? 'text-danger' : 'text-success'
						)}
					>
						{t.direction === 'DEBIT' ? '−' : '+'}{fmt.money(t.amount)}
					</Table.Cell>
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
