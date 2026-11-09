<script lang="ts">
	import ActivityIcon from '@lucide/svelte/icons/activity';
	import BadgeCheckIcon from '@lucide/svelte/icons/badge-check';
	import CreditCardIcon from '@lucide/svelte/icons/credit-card';
	import DatabaseIcon from '@lucide/svelte/icons/database';
	import FileClockIcon from '@lucide/svelte/icons/file-clock';
	import FolderTreeIcon from '@lucide/svelte/icons/folder-tree';
	import LandmarkIcon from '@lucide/svelte/icons/landmark';
	import LayoutDashboardIcon from '@lucide/svelte/icons/layout-dashboard';
	import LifeBuoyIcon from '@lucide/svelte/icons/life-buoy';
	import PercentIcon from '@lucide/svelte/icons/percent';
	import ReceiptIcon from '@lucide/svelte/icons/receipt';
	import ScaleIcon from '@lucide/svelte/icons/scale';
	import SettingsIcon from '@lucide/svelte/icons/settings';
	import ShieldAlertIcon from '@lucide/svelte/icons/shield-alert';
	import StoreIcon from '@lucide/svelte/icons/store';
	import Undo2Icon from '@lucide/svelte/icons/undo-2';
	import UsersIcon from '@lucide/svelte/icons/users';
	import WebhookIcon from '@lucide/svelte/icons/webhook';
	import DashboardShell, { type NavGroup } from '#lib/components/app/DashboardShell.svelte';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
	const t = $derived(m().admin);

	const groups = $derived<NavGroup[]>([
		{
			items: [
				{ href: '/admin', label: t.overview, icon: LayoutDashboardIcon, exact: true },
				{ href: '/admin/merchants', label: t.merchants, icon: StoreIcon },
				{ href: '/admin/customers', label: t.customers, icon: UsersIcon },
				{ href: '/admin/products', label: t.products, icon: BadgeCheckIcon },
				{ href: '/admin/categories', label: t.categories, icon: FolderTreeIcon }
			]
		},
		{
			label: m().merchant.finance,
			items: [
				{ href: '/admin/orders', label: t.orders, icon: ReceiptIcon },
				{ href: '/admin/payments', label: t.payments, icon: CreditCardIcon },
				{ href: '/admin/refunds', label: t.refunds, icon: Undo2Icon },
				{ href: '/admin/chargebacks', label: t.chargebacks, icon: ShieldAlertIcon },
				{ href: '/admin/commissions', label: t.commissions, icon: PercentIcon },
				{ href: '/admin/settlements', label: t.settlements, icon: LandmarkIcon },
				{ href: '/admin/reconciliation', label: t.reconciliation, icon: ScaleIcon }
			]
		},
		{
			label: t.settings,
			items: [
				{ href: '/admin/provider', label: t.provider, icon: ActivityIcon },
				{ href: '/admin/webhooks', label: t.webhooks, icon: WebhookIcon },
				{ href: '/admin/settings', label: t.settings, icon: SettingsIcon },
				{ href: '/admin/audit-logs', label: t.auditLogs, icon: FileClockIcon },
				{ href: '/admin/support', label: t.support, icon: LifeBuoyIcon }
			]
		},
		{
			label: m().data.title,
			items: [{ href: '/admin/data', label: m().data.nav, icon: DatabaseIcon }]
		}
	]);
</script>

<DashboardShell title={t.title} {groups}>
	{@render children()}
</DashboardShell>
