<script lang="ts">
	import type { Refund } from '#lib/api/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import StatusBadge from './StatusBadge.svelte';

	interface Props {
		refunds: Refund[];
		/** When set, REQUESTED refunds show approve/decline actions. */
		ondecide?: (refund: Refund, approve: boolean) => void;
		busy?: string | null;
	}

	let { refunds, ondecide, busy = null }: Props = $props();
</script>

<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
	<Table.Root>
		<Table.Header>
			<Table.Row>
				<Table.Head>{m().common.date}</Table.Head>
				<Table.Head>{m().common.reason}</Table.Head>
				<Table.Head>{m().merchant.initiatedBy}</Table.Head>
				<Table.Head>{m().common.status}</Table.Head>
				<Table.Head class="text-end">{m().common.amount}</Table.Head>
				{#if ondecide}<Table.Head class="text-end"
						><span class="sr-only">{m().common.actions}</span></Table.Head
					>{/if}
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each refunds as r (r.id)}
				<Table.Row>
					<Table.Cell class="text-ink-3">{fmt.datetime(r.created_at)}</Table.Cell>
					<Table.Cell class="max-w-72 whitespace-normal"
						><bdi>{r.reason}</bdi>{#if r.failure_reason}<p class="text-xs text-danger">
								{r.failure_reason}
							</p>{/if}</Table.Cell
					>
					<Table.Cell>{statusLabel(r.initiated_by)}</Table.Cell>
					<Table.Cell><StatusBadge status={r.status} /></Table.Cell>
					<Table.Cell class="text-end font-medium tabular">{fmt.money(r.amount)}</Table.Cell>
					{#if ondecide}
						<Table.Cell class="text-end">
							{#if r.status === 'REQUESTED'}
								<div class="flex justify-end gap-1">
									<Button size="sm" onclick={() => ondecide(r, true)} disabled={busy === r.id}
										>{m().merchant.approve}</Button
									>
									<Button
										size="sm"
										variant="outline"
										onclick={() => ondecide(r, false)}
										disabled={busy === r.id}>{m().merchant.decline}</Button
									>
								</div>
							{/if}
						</Table.Cell>
					{/if}
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
