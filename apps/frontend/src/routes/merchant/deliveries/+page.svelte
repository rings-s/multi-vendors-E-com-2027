<script lang="ts">
	import TruckIcon from '@lucide/svelte/icons/truck';
	import { deliveryStatusLabel } from '#lib/components/app/DeliveryCard.svelte';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().delivery.queueTitle} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().delivery.queueTitle} description={m().delivery.queueSubtitle} />
	<FilterBar>
		<Field.Field class="w-auto">
			<Field.Label for="dq-active">{m().delivery.activeOnly}</Field.Label>
			<NativeSelect.Root
				id="dq-active"
				name="active"
				value={data.filters.active ? 'true' : 'false'}
			>
				<NativeSelect.Option value="true">{m().common.yes}</NativeSelect.Option>
				<NativeSelect.Option value="false">{m().common.no}</NativeSelect.Option>
			</NativeSelect.Root>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="dq-status">{m().common.status}</Field.Label>
			<NativeSelect.Root id="dq-status" name="status" value={data.filters.status}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				{#each data.statuses as s (s)}<NativeSelect.Option value={s}
						>{m().delivery.statusLabel[s]}</NativeSelect.Option
					>{/each}
			</NativeSelect.Root>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="dq-method">{m().delivery.title}</Field.Label>
			<NativeSelect.Root id="dq-method" name="method" value={data.filters.method}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				<NativeSelect.Option value="DELIVERY">{m().delivery.method.DELIVERY}</NativeSelect.Option>
				<NativeSelect.Option value="PICKUP">{m().delivery.method.PICKUP}</NativeSelect.Option>
			</NativeSelect.Root>
		</Field.Field>
	</FilterBar>
	{#if data.deliveries.items.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().merchant.orders}</Table.Head>
						<Table.Head>{m().merchant.customer}</Table.Head>
						<Table.Head>{m().delivery.title}</Table.Head>
						<Table.Head>{m().delivery.zone}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
						<Table.Head class="text-end">{m().delivery.fee}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.deliveries.items as d (d.id)}
						<Table.Row data-testid="delivery-row">
							<Table.Cell>
								<a
									href="/merchant/orders/{d.merchant_order_id}"
									class="font-medium tabular hover:underline"
									dir="ltr">{d.merchant_order_number}</a
								>
								<p class="text-xs text-ink-3">{fmt.datetime(d.created_at)}</p>
							</Table.Cell>
							<Table.Cell><bdi>{d.customer_name}</bdi></Table.Cell>
							<Table.Cell>
								{m().delivery.method[d.method as 'DELIVERY']}
								{#if d.city}<p class="text-xs text-ink-3">
										{fmt.list([d.district, d.city])}
									</p>{/if}
							</Table.Cell>
							<Table.Cell class="text-ink-2">{d.zone_name ?? '—'}</Table.Cell>
							<Table.Cell>
								<StatusBadge status={d.status} label={deliveryStatusLabel(m(), d)} />
								{#if d.estimated_latest_at && d.status !== 'DELIVERED' && d.status !== 'CANCELLED'}
									<p class="mt-1 text-xs text-ink-3">
										{m().delivery.expectedBy({ date: fmt.datetime(d.estimated_latest_at) })}
									</p>
								{/if}
							</Table.Cell>
							<Table.Cell class="text-end tabular"
								>{d.fee === 0 ? m().delivery.free : fmt.money(d.fee)}</Table.Cell
							>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={data.deliveries.total}
			page={data.deliveries.page}
			pageSize={data.deliveries.page_size}
		/>
	{:else}
		<EmptyState icon={TruckIcon} title={m().delivery.noDeliveries} />
	{/if}
</div>
