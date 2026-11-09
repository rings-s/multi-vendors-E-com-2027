<script lang="ts">
	import ReceiptIcon from '@lucide/svelte/icons/receipt';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import MerchantOrdersTable from '#lib/components/app/MerchantOrdersTable.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const STATUSES = [
		'PENDING_PAYMENT',
		'PAID',
		'ACCEPTED',
		'PROCESSING',
		'SHIPPED',
		'DELIVERED',
		'COMPLETED',
		'REJECTED',
		'CANCELLED',
		'REFUNDED'
	];
</script>

<svelte:head><title>{m().merchant.orders} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.orders} />
	<FilterBar>
		<Field.Field class="w-auto">
			<Field.Label for="mo-status">{m().common.status}</Field.Label>
			<NativeSelect.Root id="mo-status" name="status" value={data.filters.status}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				{#each STATUSES as s (s)}<NativeSelect.Option value={s}
						>{statusLabel(s)}</NativeSelect.Option
					>{/each}
			</NativeSelect.Root>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="mo-unpaid">{m().merchant.includeUnpaid}</Field.Label>
			<NativeSelect.Root
				id="mo-unpaid"
				name="include_unpaid"
				value={data.filters.includeUnpaid ? 'true' : ''}
			>
				<NativeSelect.Option value="">{m().common.no}</NativeSelect.Option>
				<NativeSelect.Option value="true">{m().common.yes}</NativeSelect.Option>
			</NativeSelect.Root>
		</Field.Field>
	</FilterBar>
	{#if data.orders.items.length}
		<MerchantOrdersTable orders={data.orders.items} href={(o) => `/merchant/orders/${o.id}`} />
		<Paginator total={data.orders.total} page={data.orders.page} pageSize={data.orders.page_size} />
	{:else}
		<EmptyState icon={ReceiptIcon} title={m().merchant.noOrders} />
	{/if}
</div>
