<script lang="ts">
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import TransactionsTable from '#lib/components/app/TransactionsTable.svelte';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().merchant.transactions} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.transactions} />
	{#if data.transactions.items.length}
		<TransactionsTable items={data.transactions.items} />
		<Paginator
			total={data.transactions.total}
			page={data.transactions.page}
			pageSize={data.transactions.page_size}
		/>
	{:else}
		<EmptyState title={m().merchant.noTransactions} />
	{/if}
</div>
