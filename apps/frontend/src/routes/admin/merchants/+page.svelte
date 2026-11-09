<script lang="ts">
	import { goto } from '$app/navigation';
	import StoreIcon from '@lucide/svelte/icons/store';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const STATUSES = [
		'DRAFT',
		'SUBMITTED',
		'UNDER_REVIEW',
		'ADDITIONAL_INFO_REQUIRED',
		'APPROVED',
		'REJECTED',
		'SUSPENDED'
	];
</script>

<svelte:head><title>{m().admin.merchants} · {m().admin.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().admin.merchants} />
	<FilterBar>
		<Field.Field class="min-w-52 flex-1">
			<Field.Label for="am-q">{m().common.search}</Field.Label><Input
				id="am-q"
				name="q"
				type="search"
				value={data.filters.q}
			/>
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="am-status">{m().common.status}</Field.Label>
			<NativeSelect.Root id="am-status" name="status" value={data.filters.status}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				{#each STATUSES as s (s)}<NativeSelect.Option value={s}
						>{statusLabel(s)}</NativeSelect.Option
					>{/each}
			</NativeSelect.Root>
		</Field.Field>
	</FilterBar>
	{#if data.merchants.items.length}
		<div class="overflow-hidden rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().admin.business}</Table.Head>
						<Table.Head>{m().stores.city}</Table.Head>
						<Table.Head>{m().admin.submitted}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.merchants.items as mer (mer.id)}
						<Table.Row class="cursor-pointer" onclick={() => goto(`/admin/merchants/${mer.id}`)}>
							<Table.Cell>
								<a
									href="/admin/merchants/{mer.id}"
									class="font-medium hover:underline"
									onclick={(e) => e.stopPropagation()}>{mer.business_name}</a
								>
								{#if mer.store_slug}<p class="text-xs text-ink-3" dir="ltr">
										/stores/{mer.store_slug}
									</p>{/if}
							</Table.Cell>
							<Table.Cell class="text-ink-2">{mer.city ?? '—'}</Table.Cell>
							<Table.Cell class="text-ink-3">{fmt.date(mer.submitted_at)}</Table.Cell>
							<Table.Cell><StatusBadge status={mer.status} /></Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={data.merchants.total}
			page={data.merchants.page}
			pageSize={data.merchants.page_size}
		/>
	{:else}
		<EmptyState icon={StoreIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>
