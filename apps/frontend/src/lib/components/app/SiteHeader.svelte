<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import BellIcon from '@lucide/svelte/icons/bell';
	import LanguagesIcon from '@lucide/svelte/icons/languages';
	import LayoutDashboardIcon from '@lucide/svelte/icons/layout-dashboard';
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import MenuIcon from '@lucide/svelte/icons/menu';
	import MonitorIcon from '@lucide/svelte/icons/monitor';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import PackageIcon from '@lucide/svelte/icons/package';
	import ShieldIcon from '@lucide/svelte/icons/shield';
	import ShoppingBagIcon from '@lucide/svelte/icons/shopping-bag';
	import StoreIcon from '@lucide/svelte/icons/store';
	import SunIcon from '@lucide/svelte/icons/sun';
	import UserIcon from '@lucide/svelte/icons/user';
	import { api } from '#lib/api/client.js';
	import { isAdmin, isCustomer, isMerchant } from '#lib/auth.js';
	import { cart } from '#lib/cart.svelte.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.js';
	import * as NavigationMenu from '#lib/components/ui/navigation-menu/index.js';
	import * as Sheet from '#lib/components/ui/sheet/index.js';
	import { dir, fmt, locale, m } from '#lib/i18n/state.svelte.js';
	import { setLocale, setTheme, type Theme } from '#lib/prefs.js';
	import { signOut } from '#lib/session.js';
	import SearchPill from './SearchPill.svelte';
	import Wordmark from './Wordmark.svelte';

	const user = $derived(page.data.user);
	const theme = $derived((page.data.theme ?? 'system') as Theme);
	let menuOpen = $state(false);
	let unread = $state(0);
	let q = $state(page.url.searchParams.get('q') ?? '');

	const nav = $derived([
		{ href: '/stores', label: m().nav.stores },
		{ href: '/products', label: m().nav.products },
		{ href: '/services', label: m().nav.services }
	]);

	const active = (href: string) =>
		page.url.pathname === href || page.url.pathname.startsWith(href + '/');

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

	const themes = $derived([
		{ value: 'light' as Theme, label: m().common.themeLight, icon: SunIcon },
		{ value: 'dark' as Theme, label: m().common.themeDark, icon: MoonIcon },
		{ value: 'system' as Theme, label: m().common.themeSystem, icon: MonitorIcon }
	]);
	const ThemeIcon = $derived(themes.find((t) => t.value === theme)?.icon ?? MonitorIcon);
</script>

<header
	class="sticky top-0 z-40 border-b border-line/70 bg-background/90 backdrop-blur-xl supports-[backdrop-filter]:bg-background/75"
>
	<div class="container-page flex h-16 items-center gap-2 lg:gap-5">
		<Sheet.Root bind:open={menuOpen}>
			<Sheet.Trigger>
				{#snippet child({ props })}
					<Button
						{...props}
						variant="ghost"
						size="icon"
						class="lg:hidden"
						aria-label={m().common.openMenu}
					>
						<MenuIcon />
					</Button>
				{/snippet}
			</Sheet.Trigger>
			<Sheet.Content side={dir() === 'rtl' ? 'right' : 'left'} class="w-80 max-w-[85vw]">
				<Sheet.Header>
					<Sheet.Title><Wordmark size="sm" /></Sheet.Title>
					<Sheet.Description class="sr-only">{m().common.menu}</Sheet.Description>
				</Sheet.Header>
				<div class="flex flex-col gap-6 px-4 pb-6">
					<SearchPill bind:value={q} onsearch={() => (menuOpen = false)} />
					<NavigationMenu.Root
						orientation="vertical"
						viewport={false}
						aria-label={m().ui.mainNav}
						class="max-w-none flex-col items-stretch *:w-full"
					>
						<NavigationMenu.List class="flex-col items-stretch gap-0.5">
							{#each [{ href: '/', label: m().nav.home }, ...nav] as item (item.href)}
								<NavigationMenu.Item>
									<NavigationMenu.Link
										href={item.href}
										active={item.href === '/' ? page.url.pathname === '/' : active(item.href)}
										aria-current={(
											item.href === '/' ? page.url.pathname === '/' : active(item.href)
										)
											? 'page'
											: undefined}
										onclick={() => (menuOpen = false)}
										class="px-2 py-2.5 text-base"
									>
										{item.label}
									</NavigationMenu.Link>
								</NavigationMenu.Item>
							{/each}
						</NavigationMenu.List>
					</NavigationMenu.Root>
					{#if !user || !isMerchant(user)}
						<Button href="/sell" variant="outline" onclick={() => (menuOpen = false)}
							><StoreIcon data-icon="inline-start" />{m().nav.sell}</Button
						>
					{/if}
				</div>
			</Sheet.Content>
		</Sheet.Root>

		<a
			href="/"
			class="flex shrink-0 items-center rounded-full px-1 py-1 focus-visible:ring-4 focus-visible:ring-ring/20 focus-visible:outline-none"
			aria-label={m().brand.name}
		>
			<Wordmark />
		</a>

		<NavigationMenu.Root
			viewport={false}
			aria-label={m().ui.mainNav}
			class="hidden flex-none lg:flex"
		>
			<NavigationMenu.List>
				{#each nav as item (item.href)}
					<NavigationMenu.Item>
						<NavigationMenu.Link
							href={item.href}
							active={active(item.href)}
							aria-current={active(item.href) ? 'page' : undefined}
							class={NavigationMenu.navigationMenuTriggerStyle()}
						>
							{item.label}
						</NavigationMenu.Link>
					</NavigationMenu.Item>
				{/each}
			</NavigationMenu.List>
		</NavigationMenu.Root>

		<SearchPill bind:value={q} class="ms-auto hidden max-w-md flex-1 md:block" />

		<div class="ms-auto flex items-center gap-1 md:ms-0">
			<Button
				variant="ghost"
				size="sm"
				class="hidden sm:inline-flex"
				lang={locale() === 'ar' ? 'en' : 'ar'}
				onclick={() => setLocale(locale() === 'ar' ? 'en' : 'ar', !!user)}
				data-testid="locale-switch"
			>
				<LanguagesIcon data-icon="inline-start" />{m().common.switchLanguage}
			</Button>

			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					{#snippet child({ props })}
						<Button {...props} variant="ghost" size="icon" aria-label={m().common.theme}>
							<ThemeIcon />
						</Button>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content align="end">
					<DropdownMenu.RadioGroup value={theme} onValueChange={(v) => setTheme(v as Theme)}>
						{#each themes as t (t.value)}
							<DropdownMenu.RadioItem value={t.value}><t.icon />{t.label}</DropdownMenu.RadioItem>
						{/each}
					</DropdownMenu.RadioGroup>
					<DropdownMenu.Separator class="sm:hidden" />
					<DropdownMenu.Group class="sm:hidden">
						<DropdownMenu.Item onclick={() => setLocale(locale() === 'ar' ? 'en' : 'ar', !!user)}>
							<LanguagesIcon />{m().common.switchLanguage}
						</DropdownMenu.Item>
					</DropdownMenu.Group>
				</DropdownMenu.Content>
			</DropdownMenu.Root>

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
						<span class="absolute end-1 top-1 size-2 rounded-full bg-primary ring-2 ring-background"
						></span>
					{/if}
				</Button>
			{/if}

			{#if !user || isCustomer(user)}
				<Button
					href="/cart"
					variant="ghost"
					size="icon"
					class="relative"
					aria-label={m().ui.cartWithCount({ n: cart.count })}
					data-testid="cart-link"
				>
					<ShoppingBagIcon data-icon="inline-start" />
					{#if cart.count > 0}
						<Badge
							class="absolute -end-0.5 -top-0.5 h-5 min-w-5 px-1.5 tabular ring-2 ring-background"
							data-testid="cart-count"
						>
							{fmt.number(cart.count)}
						</Badge>
					{/if}
				</Button>
			{/if}

			{#if user}
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
					size="sm"
					class="hidden sm:inline-flex"
				>
					{m().nav.signIn}
				</Button>
				<Button href="/sell" variant="outline" size="sm" class="hidden xl:inline-flex"
					><StoreIcon data-icon="inline-start" />{m().nav.sell}</Button
				>
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
		</div>
	</div>
</header>
