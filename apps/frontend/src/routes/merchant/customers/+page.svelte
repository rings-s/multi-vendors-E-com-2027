<script lang="ts">
	import UsersIcon from '@lucide/svelte/icons/users';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import * as Table from '#lib/components/ui/table/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().merchant.customers} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.customers} />
	{#if data.customers.items.length}
		<div class="overflow-hidden rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().merchant.customer}</Table.Head>
						<Table.Head class="text-end">{m().nav.orders}</Table.Head>
						<Table.Head class="text-end">{m().merchant.totalSpent}</Table.Head>
						<Table.Head>{m().merchant.lastOrder}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.customers.items as c (c.customer_id)}
						<Table.Row>
							<Table.Cell class="font-medium"><bdi>{c.name}</bdi></Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.number(c.orders)}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(c.total_spent)}</Table.Cell>
							<Table.Cell class="text-ink-3">{fmt.date(c.last_order_at)}</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={data.customers.total}
			page={data.customers.page}
			pageSize={data.customers.page_size}
		/>
	{:else}
		<EmptyState icon={UsersIcon} title={m().merchant.noCustomers} />
	{/if}
</div>
