<script lang="ts">
	import BadgeCheckIcon from '@lucide/svelte/icons/badge-check';
	import BoxesIcon from '@lucide/svelte/icons/boxes';
	import ChartColumnIcon from '@lucide/svelte/icons/chart-column';
	import CreditCardIcon from '@lucide/svelte/icons/credit-card';
	import HandCoinsIcon from '@lucide/svelte/icons/hand-coins';
	import LandmarkIcon from '@lucide/svelte/icons/landmark';
	import LayoutDashboardIcon from '@lucide/svelte/icons/layout-dashboard';
	import MapPinnedIcon from '@lucide/svelte/icons/map-pinned';
	import PackageIcon from '@lucide/svelte/icons/package';
	import PercentIcon from '@lucide/svelte/icons/percent';
	import ReceiptIcon from '@lucide/svelte/icons/receipt';
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import StoreIcon from '@lucide/svelte/icons/store';
	import TruckIcon from '@lucide/svelte/icons/truck';
	import Undo2Icon from '@lucide/svelte/icons/undo-2';
	import UsersIcon from '@lucide/svelte/icons/users';
	import WarehouseIcon from '@lucide/svelte/icons/warehouse';
	import DashboardShell, { type NavGroup } from '#lib/components/app/DashboardShell.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();
	const mer = $derived(data.merchant);
	const approved = $derived(mer.status === 'APPROVED');

	const groups = $derived<NavGroup[]>([
		{
			items: [
				{
					href: '/merchant',
					label: m().merchant.dashboard,
					icon: LayoutDashboardIcon,
					exact: true
				},
				{ href: '/merchant/orders', label: m().merchant.orders, icon: ReceiptIcon },
				{ href: '/merchant/deliveries', label: m().delivery.queueTitle, icon: TruckIcon },
				{ href: '/merchant/customers', label: m().merchant.customers, icon: UsersIcon }
			]
		},
		{
			label: m().merchant.store,
			items: [
				{ href: '/merchant/products', label: m().merchant.products, icon: PackageIcon },
				{ href: '/merchant/services', label: m().merchant.services, icon: SparklesIcon },
				{ href: '/merchant/inventory', label: m().merchant.inventory, icon: WarehouseIcon },
				{ href: '/merchant/store', label: m().merchant.storeTitle, icon: StoreIcon },
				{ href: '/merchant/delivery', label: m().delivery.settingsTitle, icon: MapPinnedIcon }
			]
		},
		{
			label: m().merchant.finance,
			items: [
				{
					href: '/merchant/finance',
					label: m().merchant.earnings,
					icon: ChartColumnIcon,
					exact: true
				},
				{
					href: '/merchant/finance/transactions',
					label: m().merchant.transactions,
					icon: BoxesIcon
				},
				{
					href: '/merchant/finance/commissions',
					label: m().merchant.commissions,
					icon: PercentIcon
				},
				{
					href: '/merchant/finance/settlements',
					label: m().merchant.settlements,
					icon: LandmarkIcon
				},
				{ href: '/merchant/finance/refunds', label: m().merchant.refunds, icon: Undo2Icon }
			]
		},
		{
			label: m().merchant.settings,
			items: [
				{
					href: '/merchant/onboarding',
					label: m().merchant.onboarding,
					icon: BadgeCheckIcon,
					badge: approved ? null : '!'
				},
				{
					href: '/merchant/payment-account',
					label: m().merchant.paymentAccount,
					icon: CreditCardIcon,
					badge: approved && !mer.can_accept_payments ? '!' : null
				}
			]
		}
	]);
</script>

<DashboardShell title={mer.business_name || m().merchant.title} {groups}>
	{#snippet banner()}
		{#if !approved}
			<Alert.Root
				variant="warning"
				class="rounded-none border-x-0 border-t-0 px-4 py-3 sm:px-6"
				role="status"
				data-testid="merchant-status-banner"
			>
				<HandCoinsIcon aria-hidden="true" />
				<Alert.Description>
					{(m().merchant.statusBanner as Record<string, string>)[mer.status] ?? mer.status}
					{#if mer.status_reason}<span class="text-ink-2"> — {mer.status_reason}</span>{/if}
				</Alert.Description>
				{#if ['DRAFT', 'ADDITIONAL_INFO_REQUIRED'].includes(mer.status)}
					<Alert.Action>
						<Button href="/merchant/onboarding" size="sm" variant="outline"
							>{m().merchant.onboarding}</Button
						>
					</Alert.Action>
				{/if}
			</Alert.Root>
		{:else if !mer.can_accept_payments}
			<Alert.Root
				variant="warning"
				class="rounded-none border-x-0 border-t-0 px-4 py-3 sm:px-6"
				role="status"
			>
				<HandCoinsIcon aria-hidden="true" />
				<Alert.Description>{m().merchant.cannotAcceptPayments}</Alert.Description>
				<Alert.Action>
					<Button href="/merchant/payment-account" size="sm" variant="outline"
						>{m().merchant.setupPayments}</Button
					>
				</Alert.Action>
			</Alert.Root>
		{/if}
	{/snippet}
	{@render children()}
</DashboardShell>
