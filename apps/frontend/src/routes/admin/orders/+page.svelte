<script lang="ts">
	import ReceiptIcon from '@lucide/svelte/icons/receipt';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import MerchantOrdersTable from '#lib/components/app/MerchantOrdersTable.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const f = $derived(data.filters);
	const t = $derived(m().admin);
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

<svelte:head><title>{t.orders} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.orders} />
	<FilterBar>
		<Field.Field class="w-44">
			<Field.Label for="ao-num">{m().orders.number}</Field.Label><Input
				id="ao-num"
				name="number"
				dir="ltr"
				value={f.number}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="ao-status">{m().common.status}</Field.Label>
			<NativeSelect.Root id="ao-status" name="status" value={f.status}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				{#each STATUSES as s (s)}<NativeSelect.Option value={s}
						>{statusLabel(s)}</NativeSelect.Option
					>{/each}
			</NativeSelect.Root>
		</Field.Field>
		<Field.Field class="w-72">
			<Field.Label for="ao-mer">{t.merchantId}</Field.Label><Input
				id="ao-mer"
				name="merchant_id"
				dir="ltr"
				value={f.merchant_id}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="ao-from">{t.dateFrom}</Field.Label><Input
				id="ao-from"
				name="date_from"
				type="date"
				value={f.date_from}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="ao-to">{t.dateTo}</Field.Label><Input
				id="ao-to"
				name="date_to"
				type="date"
				value={f.date_to}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="ao-cr">{t.cancellationRequested}</Field.Label>
			<NativeSelect.Root id="ao-cr" name="cancellation_requested" value={f.cancellation_requested}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				<NativeSelect.Option value="true">{m().common.yes}</NativeSelect.Option>
			</NativeSelect.Root>
		</Field.Field>
	</FilterBar>
	{#if data.orders.items.length}
		<MerchantOrdersTable orders={data.orders.items} href={(o) => `/admin/orders/${o.order_id}`} />
		<Paginator total={data.orders.total} page={data.orders.page} pageSize={data.orders.page_size} />
	{:else}
		<EmptyState icon={ReceiptIcon} title={m().merchant.noOrders} />
	{/if}
</div>
