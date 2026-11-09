<script lang="ts">
	import { isolate } from '#lib/i18n/bidi.js';
	import { page } from '$app/state';
	import BellIcon from '@lucide/svelte/icons/bell';
	import LayoutDashboardIcon from '@lucide/svelte/icons/layout-dashboard';
	import MailWarningIcon from '@lucide/svelte/icons/mail-warning';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import PackageIcon from '@lucide/svelte/icons/package';
	import ShieldIcon from '@lucide/svelte/icons/shield';
	import { isAdmin, isMerchant } from '#lib/auth.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import OrderList from '#lib/components/app/OrderList.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const user = $derived(page.data.user!);
	const shortcuts = $derived([
		{
			href: '/account/orders',
			label: m().account.orders,
			icon: PackageIcon,
			count: data.orders?.total ?? null
		},
		{ href: '/account/addresses', label: m().account.addresses, icon: MapPinIcon, count: null },
		{
			href: '/account/notifications',
			label: m().account.notifications,
			icon: BellIcon,
			count: null
		}
	]);
</script>

<svelte:head><title>{m().account.title} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-10">
	<PageHeader
		title={m().account.hello({ name: isolate(user.full_name.split(' ')[0]) })}
		description={user.email}
	/>

	{#if !user.email_verified}
		<Alert.Root>
			<MailWarningIcon />
			<Alert.Title>{m().auth.verifyBanner}</Alert.Title>
			<Alert.Description
				><a href="/verify-email" class="underline underline-offset-2">{m().auth.resend}</a
				></Alert.Description
			>
		</Alert.Root>
	{/if}

	{#if isMerchant(user) || isAdmin(user)}
		<div class="flex flex-wrap gap-3">
			{#if isMerchant(user)}<Button href="/merchant"
					><LayoutDashboardIcon data-icon="inline-start" />{m().nav.merchantDashboard}</Button
				>{/if}
			{#if isAdmin(user)}<Button href="/admin" variant="outline"
					><ShieldIcon data-icon="inline-start" />{m().nav.adminDashboard}</Button
				>{/if}
		</div>
	{/if}

	{#if data.orders}
		<section class="flex flex-col gap-4">
			<div class="flex items-end justify-between">
				<h2 class="type-title">{m().account.recentOrders}</h2>
				{#if data.orders.total > 0}<Button
						href="/account/orders"
						variant="link"
						size="sm"
						class="px-0">{m().common.viewAll}</Button
					>{/if}
			</div>
			{#if data.orders.items.length}
				<OrderList orders={data.orders.items} />
			{:else}
				<EmptyState icon={PackageIcon} title={m().account.noOrders}>
					<Button href="/stores">{m().cart.continueShopping}</Button>
				</EmptyState>
			{/if}
		</section>

		<Item.Group class="grid gap-4 sm:grid-cols-3">
			{#each shortcuts as s (s.href)}
				<Item.Root variant="outline" role="listitem" class="rounded-2xl bg-surface p-5">
					{#snippet child({ props })}
						<a href={s.href} {...props}>
							<Item.Media variant="icon" class="text-primary"><s.icon /></Item.Media>
							<Item.Content>
								<Item.Title>{s.label}</Item.Title>
								{#if s.count != null}<Item.Description class="tabular"
										>{fmt.number(s.count)}</Item.Description
									>{/if}
							</Item.Content>
						</a>
					{/snippet}
				</Item.Root>
			{/each}
		</Item.Group>
	{/if}
</div>
