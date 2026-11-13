<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import BellIcon from '@lucide/svelte/icons/bell';
	import LayoutDashboardIcon from '@lucide/svelte/icons/layout-dashboard';
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import MenuIcon from '@lucide/svelte/icons/menu';
	import PackageIcon from '@lucide/svelte/icons/package';
	import ShieldIcon from '@lucide/svelte/icons/shield';
	import ShoppingBagIcon from '@lucide/svelte/icons/shopping-bag';
	import StoreIcon from '@lucide/svelte/icons/store';
	import UserIcon from '@lucide/svelte/icons/user';
	import { api } from '#lib/api/client.js';
	import type { Category } from '#lib/api/types.js';
	import { isAdmin, isCustomer, isMerchant } from '#lib/auth.js';
	import { cart } from '#lib/cart.svelte.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.js';
	import * as Sheet from '#lib/components/ui/sheet/index.js';
	import { trackIndicator } from '#lib/indicator.js';
	import { dir, fmt, m, pick } from '#lib/i18n/state.svelte.js';
	import { signOut } from '#lib/session.js';
	import { cn } from '#lib/utils.js';
	import PrefToggles from './PrefToggles.svelte';
	import SearchPill from './SearchPill.svelte';
	import Wordmark from './Wordmark.svelte';

	const user = $derived(page.data.user);
	const categories = $derived((page.data.navCategories ?? []) as Category[]);
	let menuOpen = $state(false);
	let unread = $state(0);
	let q = $state(page.url.searchParams.get('q') ?? '');

	const path = $derived(page.url.pathname);
	const category = $derived(page.url.searchParams.get('category'));
	const under = (href: string) => path === href || path.startsWith(href + '/');

	/** One tab row: the fixed sections, then every top-level category. Exactly one is current. */
	const tabs = $derived([
		{ key: 'home', href: '/', label: m().nav.home, current: path === '/' },
		{ key: 'stores', href: '/stores', label: m().nav.stores, current: under('/stores') },
		{
			key: 'products',
			href: '/products',
			label: m().nav.products,
			current: under('/products') && !category
		},
		{
			key: 'services',
			href: '/services',
			label: m().nav.services,
			current: under('/services') && !category
		},
		...categories.map((c) => ({
			key: c.id,
			href: `/${c.kind === 'SERVICE' ? 'services' : 'products'}?category=${c.slug}`,
			label: pick(c, 'name'),
			current: (path === '/products' || path === '/services') && category === c.slug,
			category: true
		}))
	]);
	const firstCategory = $derived(tabs.findIndex((t) => 'category' in t));

	$effect(() => {
		if (user && isCustomer(user)) void cart.refresh();
		else cart.clear();
	});

	$effect(() => {
		if (!user) return;
		void page.url.pathname; // refresh the unread count on navigation
		api
			.GET('/api/v1/notifications', { params: { query: { unread_only: true, page_size: 1 } } })
			.then(({ data }) => (unread = data?.unread ?? 0))
			.catch(() => {});
	});

	/** Keep the chosen tab in view when the row scrolls (phones, many categories). */
	function revealCurrent(node: HTMLElement) {
		$effect(() => {
			void path;
			void category;
			const current = node.querySelector<HTMLElement>('[aria-current="page"]');
			if (!current || node.scrollWidth <= node.clientWidth) return;
			const a = node.getBoundingClientRect();
			const b = current.getBoundingClientRect();
			node.scrollBy({ left: b.left + b.width / 2 - (a.left + a.width / 2), behavior: 'smooth' });
		});
	}
</script>

<header
	class="sticky top-0 z-40 border-b border-line bg-background lg:border-b-0"
	style="view-transition-name: site-header"
>
	<div class="container-page flex h-16 items-center gap-2 lg:gap-6">
		<Sheet.Root bind:open={menuOpen}>
			<Sheet.Trigger>
				{#snippet child({ props })}
					<Button
						{...props}
						variant="ghost"
						size="icon"
						class="-ms-2 lg:hidden"
						aria-label={m().common.openMenu}
					>
						<MenuIcon />
					</Button>
				{/snippet}
			</Sheet.Trigger>
			<Sheet.Content side={dir() === 'rtl' ? 'right' : 'left'} class="w-80 max-w-[88vw] gap-0">
				<Sheet.Header class="border-b border-line">
					<Sheet.Title><Wordmark size="sm" /></Sheet.Title>
					<Sheet.Description class="sr-only">{m().common.menu}</Sheet.Description>
				</Sheet.Header>
				<div class="flex flex-1 flex-col gap-6 overflow-y-auto p-4">
					<nav aria-label={m().ui.mainNav}>
						<ul
							data-indicator="pill"
							class="flex flex-col gap-0.5 [--ind-bg:var(--muted)] [--ind-shadow:none]"
							{@attach (node) => trackIndicator(node)}
						>
							{#each tabs as tab, i (tab.key)}
								{#if i === firstCategory}
									<li class="px-3 pt-4 pb-1 type-caption text-ink-3" aria-hidden="true">
										{m().nav.categories}
									</li>
								{/if}
								<li>
									<a
										href={tab.href}
										aria-current={tab.current ? 'page' : undefined}
										onclick={() => (menuOpen = false)}
										class="flex h-11 items-center rounded-lg px-3 text-[0.9375rem] text-ink-2 transition-colors outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-ring/60 aria-[current=page]:font-medium aria-[current=page]:text-ink"
									>
										<bdi>{tab.label}</bdi>
									</a>
								</li>
							{/each}
						</ul>
					</nav>
					<div class="mt-auto flex flex-col gap-3">
						<PrefToggles expanded testable={false} />
						{#if !user || !isMerchant(user)}
							<Button href="/sell" variant="outline" onclick={() => (menuOpen = false)}
								><StoreIcon data-icon="inline-start" />{m().nav.sell}</Button
							>
						{/if}
					</div>
				</div>
			</Sheet.Content>
		</Sheet.Root>

		<a
			href="/"
			class="flex shrink-0 items-center rounded-md py-1 outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
			aria-label={m().brand.name}
		>
			<Wordmark />
		</a>

		<SearchPill bind:value={q} class="mx-auto hidden max-w-2xl flex-1 md:block" />

		<div class="ms-auto flex items-center gap-1 md:ms-0 lg:gap-2">
			<div class="hidden items-center gap-2 lg:flex">
				<PrefToggles />
			</div>

			{#if user}
				<Button
					href="/account/notifications"
					variant="ghost"
					size="icon"
					class="relative"
					aria-label={unread ? m().ui.unreadNotifications({ n: unread }) : m().nav.notifications}
				>
					<BellIcon />
					{#if unread}
						<span class="absolute end-2 top-2 size-2 rounded-full bg-sale ring-2 ring-background"
						></span>
					{/if}
				</Button>
				<DropdownMenu.Root>
					<DropdownMenu.Trigger>
						{#snippet child({ props })}
							<Button
								{...props}
								variant="ghost"
								size="icon"
								aria-label={m().ui.accountMenu}
								data-testid="user-menu"
							>
								<UserIcon />
							</Button>
						{/snippet}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content align="end" class="w-60">
						<DropdownMenu.Group>
							<DropdownMenu.Label class="font-normal">
								<p class="truncate text-sm font-medium text-ink"><bdi>{user.full_name}</bdi></p>
								<p class="truncate text-xs text-ink-3">{user.email}</p>
							</DropdownMenu.Label>
						</DropdownMenu.Group>
						<DropdownMenu.Separator />
						<DropdownMenu.Group>
							{#if isAdmin(user)}
								<DropdownMenu.Item onclick={() => goto('/admin')}
									><ShieldIcon />{m().nav.adminDashboard}</DropdownMenu.Item
								>
							{/if}
							{#if isMerchant(user)}
								<DropdownMenu.Item onclick={() => goto('/merchant')}>
									<LayoutDashboardIcon />{m().nav.merchantDashboard}
								</DropdownMenu.Item>
							{/if}
							{#if isCustomer(user)}
								<DropdownMenu.Item onclick={() => goto('/account')}
									><UserIcon />{m().nav.account}</DropdownMenu.Item
								>
								<DropdownMenu.Item onclick={() => goto('/account/orders')}
									><PackageIcon />{m().nav.orders}</DropdownMenu.Item
								>
							{/if}
						</DropdownMenu.Group>
						<DropdownMenu.Separator />
						<DropdownMenu.Group>
							<DropdownMenu.Item onclick={signOut} data-testid="sign-out"
								><LogOutIcon />{m().nav.signOut}</DropdownMenu.Item
							>
						</DropdownMenu.Group>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			{:else}
				<Button
					href="/sign-in?next={encodeURIComponent(page.url.pathname + page.url.search)}"
					variant="ghost"
					class="hidden sm:inline-flex"
				>
					{m().nav.signIn}
				</Button>
				<Button
					href="/sign-in"
					variant="ghost"
					size="icon"
					class="sm:hidden"
					aria-label={m().nav.signIn}
				>
					<UserIcon />
				</Button>
			{/if}

			{#if !user || isCustomer(user)}
				<Button
					href="/cart"
					variant="outline"
					class={cn('relative', cart.count > 0 ? 'gap-2 px-3' : 'w-10 px-0')}
					aria-label={m().ui.cartWithCount({ n: cart.count })}
					data-testid="cart-link"
				>
					<ShoppingBagIcon />
					{#if cart.count > 0}
						<span
							class="grid h-5 min-w-5 place-items-center rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground tabular"
							data-testid="cart-count"
						>
							{fmt.number(cart.count)}
						</span>
					{/if}
				</Button>
			{/if}
		</div>
	</div>
	<div class="container-page pb-3 md:hidden">
		<SearchPill bind:value={q} />
	</div>
</header>

<!-- Section and category tabs: one row, one sliding rule under the current tab. -->
<nav
	aria-label={m().ui.mainNav}
	class="z-30 border-b border-line bg-background lg:sticky lg:top-16"
	style="view-transition-name: site-tabs"
>
	<div class="container-page flex items-stretch gap-6">
		<ul
			data-indicator="line"
			class="-mx-1 flex h-11 min-w-0 flex-1 [scrollbar-width:none] items-stretch gap-1 overflow-x-auto px-1 [--ind-bg:var(--primary)] [&::-webkit-scrollbar]:hidden"
			{@attach (node) => trackIndicator(node)}
			{@attach revealCurrent}
		>
			{#each tabs as tab, i (tab.key)}
				{#if i === firstCategory}
					<li class="my-3 w-px shrink-0 bg-line-strong" aria-hidden="true"></li>
				{/if}
				<li class="flex shrink-0">
					<a
						href={tab.href}
						aria-current={tab.current ? 'page' : undefined}
						class="flex items-center px-2.5 text-sm whitespace-nowrap text-ink-2 transition-colors duration-150 outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-inset aria-[current=page]:font-medium aria-[current=page]:text-ink"
					>
						<bdi>{tab.label}</bdi>
					</a>
				</li>
			{/each}
		</ul>
		{#if !user || !isMerchant(user)}
			<a
				href="/sell"
				class="hidden shrink-0 items-center gap-1.5 text-sm font-medium text-primary outline-none hover:underline hover:underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring/60 lg:flex"
			>
				<StoreIcon class="size-4" aria-hidden="true" />{m().nav.sell}
			</a>
		{/if}
	</div>
</nav>
