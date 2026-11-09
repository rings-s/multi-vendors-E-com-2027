<script lang="ts">
	import { goto } from '$app/navigation';
	import CreditCardIcon from '@lucide/svelte/icons/credit-card';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const f = $derived(data.filters);
	const t = $derived(m().admin);
	const STATUSES = [
		'CREATED',
		'PENDING',
		'AUTHORIZED',
		'PAID',
		'FAILED',
		'CANCELLED',
		'PARTIALLY_REFUNDED',
		'REFUNDED',
		'DISPUTED'
	];
</script>

<svelte:head><title>{t.payments} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.payments} />
	<FilterBar>
		<Field.Field class="w-56">
			<Field.Label for="ap-ref">{t.reference}</Field.Label><Input
				id="ap-ref"
				name="reference"
				dir="ltr"
				value={f.reference}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="ap-status">{m().common.status}</Field.Label>
			<NativeSelect.Root id="ap-status" name="status" value={f.status}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				{#each STATUSES as s (s)}<NativeSelect.Option value={s}
						>{statusLabel(s)}</NativeSelect.Option
					>{/each}
			</NativeSelect.Root>
		</Field.Field>
		<Field.Field class="w-72">
			<Field.Label for="ap-mer">{t.merchantId}</Field.Label><Input
				id="ap-mer"
				name="merchant_id"
				dir="ltr"
				value={f.merchant_id}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="ap-test">{m().common.testMode}</Field.Label>
			<NativeSelect.Root id="ap-test" name="is_test" value={f.is_test}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				<NativeSelect.Option value="true">{m().common.yes}</NativeSelect.Option>
				<NativeSelect.Option value="false">{m().common.no}</NativeSelect.Option>
			</NativeSelect.Root>
		</Field.Field>
	</FilterBar>
	{#if data.payments.items.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{t.reference}</Table.Head>
						<Table.Head>{m().common.date}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
						<Table.Head class="text-end">{m().common.amount}</Table.Head>
						<Table.Head class="text-end">{m().orders.refunded}</Table.Head>
						<Table.Head class="text-end">{m().merchant.fee}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.payments.items as p (p.id)}
						<Table.Row class="cursor-pointer" onclick={() => goto(`/admin/payments/${p.id}`)}>
							<Table.Cell
								><a
									href="/admin/payments/{p.id}"
									class="font-medium tabular hover:underline"
									dir="ltr"
									onclick={(e) => e.stopPropagation()}
									>{p.provider_payment_id ?? p.id.slice(0, 8)}</a
								>{#if p.is_test}<Badge variant="warning" class="ms-1.5">{m().common.testMode}</Badge
									>{/if}</Table.Cell
							>
							<Table.Cell class="text-ink-3">{fmt.datetime(p.created_at)}</Table.Cell>
							<Table.Cell><StatusBadge status={p.status} /></Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(p.amount)}</Table.Cell>
							<Table.Cell class="text-end tabular"
								>{p.refunded_amount ? fmt.money(p.refunded_amount) : '—'}</Table.Cell
							>
							<Table.Cell class="text-end tabular"
								>{p.fee == null ? '—' : fmt.money(p.fee)}</Table.Cell
							>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={data.payments.total}
			page={data.payments.page}
			pageSize={data.payments.page_size}
		/>
	{:else}
		<EmptyState icon={CreditCardIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>
