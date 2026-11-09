<script lang="ts">
	import PackageIcon from '@lucide/svelte/icons/package';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import OrderList from '#lib/components/app/OrderList.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().orders.title} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().orders.title} />
	{#if data.orders.items.length}
		<OrderList orders={data.orders.items} />
		<Paginator total={data.orders.total} page={data.orders.page} pageSize={data.orders.page_size} />
	{:else}
		<EmptyState icon={PackageIcon} title={m().orders.empty}>
			<Button href="/stores">{m().cart.continueShopping}</Button>
		</EmptyState>
	{/if}
</div>
