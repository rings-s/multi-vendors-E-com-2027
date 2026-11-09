<script lang="ts" module>
	import type { Component } from 'svelte';

	export interface NavItem {
		href: string;
		label: string;
		icon: Component;
		/** Match only this exact path (for index routes). */
		exact?: boolean;
		badge?: string | number | null;
	}
	export interface NavGroup {
		label?: string;
		items: NavItem[];
	}
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import ArrowUpRightIcon from '@lucide/svelte/icons/arrow-up-right';
	import LanguagesIcon from '@lucide/svelte/icons/languages';
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import MonitorIcon from '@lucide/svelte/icons/monitor';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import SunIcon from '@lucide/svelte/icons/sun';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import * as Sidebar from '#lib/components/ui/sidebar/index.js';
	import { dir, locale, m } from '#lib/i18n/state.svelte.js';
	import { setLocale, setTheme, type Theme } from '#lib/prefs.js';
	import { signOut } from '#lib/session.js';
	import SidebarAutoClose from './SidebarAutoClose.svelte';
	import Logo from './Logo.svelte';
	import Wordmark from './Wordmark.svelte';

	interface Props {
		title: string;
		groups: NavGroup[];
		banner?: Snippet;
		children: Snippet;
	}

	let { title, groups, banner, children }: Props = $props();
	const user = $derived(page.data.user);
	// Desktop: expanded ⇄ 64px icon rail (button, rail edge or Ctrl/⌘+B). Mobile: off-canvas sheet.
	let sidebarOpen = $state(page.data.sidebarOpen ?? true);
	const theme = $derived((page.data.theme ?? 'system') as Theme);
	const nextTheme: Record<Theme, Theme> = { light: 'dark', dark: 'system', system: 'light' };
	const ThemeIcon = $derived(
		theme === 'light' ? SunIcon : theme === 'dark' ? MoonIcon : MonitorIcon
	);

	const isActive = (item: NavItem) =>
		item.exact
			? page.url.pathname === item.href
			: page.url.pathname === item.href || page.url.pathname.startsWith(item.href + '/');
</script>

<Sidebar.Provider bind:open={sidebarOpen}>
	<SidebarAutoClose />
	<!-- `side="left"` is the inline-start edge; it mirrors in RTL. -->
	<Sidebar.Root side="left" collapsible="icon" title={m().brand.name} description={title}>
		<Sidebar.Header
			class="gap-1.5 px-5 pt-6 pb-4 transition-[padding] group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-2"
		>
			<a
				href="/"
				class="w-fit rounded-full focus-visible:ring-4 focus-visible:ring-ring/20 focus-visible:outline-none"
				aria-label={m().brand.name}
			>
				<Wordmark size="sm" class="group-data-[collapsible=icon]:hidden" />
				<!-- Collapsed rail: the logo mark alone. -->
				<Logo class="hidden size-8 text-ink group-data-[collapsible=icon]:block" />
			</a>
			<p class="type-label text-ink-3 group-data-[collapsible=icon]:hidden"><bdi>{title}</bdi></p>
		</Sidebar.Header>
		<Sidebar.Content>
			<nav aria-label={title} class="contents">
				{#each groups as group, gi (gi)}
					<Sidebar.Group>
						{#if group.label}
							<Sidebar.GroupLabel>{group.label}</Sidebar.GroupLabel>
						{/if}
						<Sidebar.GroupContent>
							<Sidebar.Menu>
								{#each group.items as item (item.href)}
									<Sidebar.MenuItem>
										<Sidebar.MenuButton
											isActive={isActive(item)}
											tooltipContent={item.label}
											tooltipContentProps={{ side: dir() === 'rtl' ? 'left' : 'right' }}
										>
											{#snippet child({ props })}
												<a
													href={item.href}
													aria-current={isActive(item) ? 'page' : undefined}
													{...props}
												>
													<item.icon aria-hidden="true" />
													<span>{item.label}</span>
												</a>
											{/snippet}
										</Sidebar.MenuButton>
										{#if item.badge}
											<Sidebar.MenuBadge class="tabular">{item.badge}</Sidebar.MenuBadge>
										{/if}
									</Sidebar.MenuItem>
								{/each}
							</Sidebar.Menu>
						</Sidebar.GroupContent>
					</Sidebar.Group>
				{/each}
			</nav>
		</Sidebar.Content>
		<Sidebar.Rail aria-label={m().ui.toggleSidebar} title={m().ui.toggleSidebar} />
	</Sidebar.Root>

	<Sidebar.Inset class="min-w-0 bg-surface-2">
		<header
			class="sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-line/70 bg-surface-2/80 px-4 backdrop-blur-xl sm:px-6"
		>
			<Sidebar.Trigger class="-ms-1" aria-label={m().ui.toggleSidebar} />
			<Separator orientation="vertical" class="h-4" />
			<p class="truncate font-medium text-ink"><bdi>{title}</bdi></p>

			<div class="ms-auto flex items-center gap-1">
				<Button href="/" variant="ghost" size="sm" class="hidden sm:inline-flex">
					{m().nav.home}<ArrowUpRightIcon class="rtl-flip" data-icon="inline-end" />
				</Button>
				<Button
					variant="ghost"
					size="sm"
					lang={locale() === 'ar' ? 'en' : 'ar'}
					onclick={() => setLocale(locale() === 'ar' ? 'en' : 'ar', !!user)}
					data-testid="locale-switch"
				>
					<LanguagesIcon data-icon="inline-start" /><span class="hidden sm:inline"
						>{m().common.switchLanguage}</span
					>
				</Button>
				<Button
					variant="ghost"
					size="icon"
					aria-label="{m().common.theme}: {m().common[
						theme === 'light' ? 'themeLight' : theme === 'dark' ? 'themeDark' : 'themeSystem'
					]}"
					onclick={() => setTheme(nextTheme[theme])}
				>
					<ThemeIcon />
				</Button>
				{#if user}
					<span class="hidden max-w-40 truncate px-2 text-sm text-ink-2 md:inline"
						><bdi>{user.full_name}</bdi></span
					>
				{/if}
				<Button
					variant="ghost"
					size="icon"
					aria-label={m().nav.signOut}
					onclick={signOut}
					data-testid="sign-out"
				>
					<LogOutIcon class="rtl-flip" />
				</Button>
			</div>
		</header>
		{@render banner?.()}
		<main id="main" class="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-10">
			{@render children()}
		</main>
	</Sidebar.Inset>
</Sidebar.Provider>
