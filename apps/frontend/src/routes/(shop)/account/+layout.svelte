<script lang="ts">
	import { page } from '$app/state';
	import BellIcon from '@lucide/svelte/icons/bell';
	import LayoutGridIcon from '@lucide/svelte/icons/layout-grid';
	import LifeBuoyIcon from '@lucide/svelte/icons/life-buoy';
	import LockIcon from '@lucide/svelte/icons/lock';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import PackageIcon from '@lucide/svelte/icons/package';
	import UserIcon from '@lucide/svelte/icons/user';
	import { isCustomer } from '#lib/auth.js';
	import { trackIndicator } from '#lib/indicator.js';
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

<div class="container-page grid gap-8 py-8 lg:grid-cols-[15rem_1fr] lg:gap-12 lg:py-12">
	<div class="flex min-w-0 flex-col gap-3 lg:sticky lg:top-32 lg:self-start">
		<p class="hidden px-3 text-lg font-semibold text-ink lg:block">{m().account.title}</p>
		<nav aria-label={m().account.title} class="-mx-4 overflow-x-auto px-4 lg:mx-0 lg:px-0">
			<!-- A scrolling row of tabs on phones, a side list on desktop; one marker follows the page. -->
			<ul
				data-indicator="pill"
				class="flex w-max gap-0.5 rounded-lg bg-muted p-0.5 [--ind-radius:7px] lg:w-full lg:flex-col lg:bg-transparent lg:p-0 lg:[--ind-bg:var(--muted)] lg:[--ind-radius:10px] lg:[--ind-shadow:none]"
				{@attach (node) => trackIndicator(node)}
			>
				{#each items as item (item.href)}
					<li>
						<a
							href={item.href}
							aria-current={active(item.href, item.exact) ? 'page' : undefined}
							class="flex h-9 items-center gap-2.5 rounded-[7px] px-3 text-sm whitespace-nowrap text-ink-2 transition-colors duration-150 outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-ring/60 aria-[current=page]:font-medium aria-[current=page]:text-ink lg:h-10 lg:rounded-lg"
						>
							<item.icon class="size-4 shrink-0" aria-hidden="true" />{item.label}
						</a>
					</li>
				{/each}
			</ul>
		</nav>
	</div>
	<div class="min-w-0">{@render children()}</div>
</div>
