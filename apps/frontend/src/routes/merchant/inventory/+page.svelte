<script lang="ts">
	import WarehouseIcon from '@lucide/svelte/icons/warehouse';
	import { api, call } from '#lib/api/client.js';
	import type { Inventory } from '#lib/api/types.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as ButtonGroup from '#lib/components/ui/button-group/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	let rows = $state<Inventory[]>([]);
	let drafts = $state<Record<string, string>>({});
	let saving = $state<string | null>(null);
	let q = $state('');

	$effect.pre(() => {
		rows = data.inventory;
		drafts = Object.fromEntries(data.inventory.map((r) => [r.id, String(r.quantity_on_hand)]));
	});

	const shown = $derived(
		q.trim()
			? rows.filter((r) =>
					`${r.product_title} ${r.variant_name ?? ''} ${r.sku}`
						.toLowerCase()
						.includes(q.trim().toLowerCase())
				)
			: rows
	);

	async function set(row: Inventory) {
		const qty = Math.floor(Number(drafts[row.id]));
		if (!(qty >= 0)) return;
		saving = row.id;
		const updated = await action(
			() =>
				call(
					api.PATCH('/api/v1/merchant/inventory/{inventory_id}', {
						params: { path: { inventory_id: row.id } },
						body: { quantity_on_hand: qty }
					})
				),
			m().common.saved
		);
		saving = null;
		if (updated) {
			// The endpoint returns the refreshed inventory list.
			rows = updated;
			drafts = Object.fromEntries(updated.map((r) => [r.id, String(r.quantity_on_hand)]));
		}
	}
</script>

<svelte:head><title>{m().merchant.inventory} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.inventory}>
		{#snippet actions()}<Input
				type="search"
				bind:value={q}
				placeholder={m().common.search}
				aria-label={m().common.search}
				class="w-56"
			/>{/snippet}
	</PageHeader>
	{#if rows.length}
		<div class="overflow-hidden rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().merchant.productTitle}</Table.Head>
						<Table.Head>{m().catalog.sku}</Table.Head>
						<Table.Head class="text-end">{m().merchant.reserved}</Table.Head>
						<Table.Head class="text-end">{m().merchant.available}</Table.Head>
						<Table.Head class="w-56">{m().merchant.onHand}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each shown as r (r.id)}
						<Table.Row>
							<Table.Cell>
								<a href="/merchant/products/{r.product_id}" class="font-medium hover:underline"
									><bdi>{r.product_title}</bdi></a
								>
								{#if r.variant_name}<p class="text-xs text-ink-3">{r.variant_name}</p>{/if}
							</Table.Cell>
							<Table.Cell class="text-ink-2" dir="ltr">{r.sku}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.number(r.quantity_reserved)}</Table.Cell>
							<Table.Cell
								class={cn(
									'text-end font-medium tabular',
									r.available === 0 && 'text-danger',
									r.available > 0 && r.available <= 5 && 'text-warning'
								)}>{fmt.number(r.available)}</Table.Cell
							>
							<Table.Cell>
								<form
									onsubmit={(e) => {
										e.preventDefault();
										set(r);
									}}
								>
									<ButtonGroup.Root>
										<Input
											type="number"
											min={r.quantity_reserved}
											bind:value={drafts[r.id]}
											class="w-24"
											aria-label="{m().merchant.onHand}: {r.product_title}"
										/>
										<Button
											type="submit"
											variant="outline"
											disabled={saving === r.id || drafts[r.id] === String(r.quantity_on_hand)}
											>{m().merchant.setQuantity}</Button
										>
									</ButtonGroup.Root>
								</form>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{:else}
		<EmptyState icon={WarehouseIcon} title={m().merchant.noInventory} />
	{/if}
</div>
