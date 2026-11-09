<script lang="ts">
	import * as NavigationMenu from '#lib/components/ui/navigation-menu/index.js';
	import { page } from '$app/state';
	import BellIcon from '@lucide/svelte/icons/bell';
	import LayoutGridIcon from '@lucide/svelte/icons/layout-grid';
	import LifeBuoyIcon from '@lucide/svelte/icons/life-buoy';
	import LockIcon from '@lucide/svelte/icons/lock';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import PackageIcon from '@lucide/svelte/icons/package';
	import UserIcon from '@lucide/svelte/icons/user';
	import { isCustomer } from '#lib/auth.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
	const user = $derived(page.data.user);
	const customer = $derived(isCustomer(user));

	const items = $derived(
		[
			{
				href: '/account',
				label: m().account.overview,
				icon: LayoutGridIcon,
				exact: true,
				show: true
			},
			{ href: '/account/orders', label: m().account.orders, icon: PackageIcon, show: customer },
			{
				href: '/account/addresses',
				label: m().account.addresses,
				icon: MapPinIcon,
				show: customer
			},
			{ href: '/account/profile', label: m().account.profile, icon: UserIcon, show: true },
			{
				href: '/account/notifications',
				label: m().account.notifications,
				icon: BellIcon,
				show: true
			},
			{ href: '/account/security', label: m().account.security, icon: LockIcon, show: true },
			{ href: '/account/support', label: m().account.support, icon: LifeBuoyIcon, show: true }
		].filter((i) => i.show)
	);

	const active = (href: string, exact?: boolean) =>
		exact
			? page.url.pathname === href
			: page.url.pathname === href || page.url.pathname.startsWith(href + '/');
</script>

<div class="container-page grid gap-8 py-10 lg:grid-cols-[14rem_1fr] lg:gap-12">
	<div class="flex min-w-0 flex-col gap-3 lg:sticky lg:top-24 lg:self-start">
		<p class="hidden font-display text-xl text-ink lg:block">{m().account.title}</p>
		<NavigationMenu.Root
			viewport={false}
			aria-label={m().account.title}
			class="max-w-full justify-start overflow-x-auto pb-1 *:w-full lg:overflow-visible"
		>
			<NavigationMenu.List class="justify-start lg:flex-col lg:items-stretch">
				{#each items as item (item.href)}
					<NavigationMenu.Item>
						<NavigationMenu.Link
							href={item.href}
							active={active(item.href, item.exact)}
							aria-current={active(item.href, item.exact) ? 'page' : undefined}
							class="px-3 whitespace-nowrap"
						>
							<item.icon aria-hidden="true" />{item.label}
						</NavigationMenu.Link>
					</NavigationMenu.Item>
				{/each}
			</NavigationMenu.List>
		</NavigationMenu.Root>
	</div>
	<div class="min-w-0">{@render children()}</div>
</div>
