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
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import * as Sidebar from '#lib/components/ui/sidebar/index.js';
	import { trackIndicator } from '#lib/indicator.js';
	import { dir, m } from '#lib/i18n/state.svelte.js';
	import { signOut } from '#lib/session.js';
	import SidebarAutoClose from './SidebarAutoClose.svelte';
	import Logo from './Logo.svelte';
	import PrefToggles from './PrefToggles.svelte';
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
				class="w-fit rounded-md focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:outline-none"
				aria-label={m().brand.name}
			>
				<Wordmark size="sm" class="group-data-[collapsible=icon]:hidden" />
				<!-- Collapsed rail: the logo mark alone. -->
				<Logo class="hidden size-8 text-primary group-data-[collapsible=icon]:block" />
			</a>
			<p class="type-label text-ink-3 group-data-[collapsible=icon]:hidden"><bdi>{title}</bdi></p>
		</Sidebar.Header>
		<Sidebar.Content>
			<nav
				aria-label={title}
				data-indicator="pill"
				class="flex flex-col [--ind-bg:var(--sidebar-accent)] [--ind-radius:10px] [--ind-shadow:none]"
				{@attach (node) => trackIndicator(node, '[aria-current="page"]')}
			>
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
			class="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-line bg-background px-4 sm:px-6"
		>
			<Sidebar.Trigger class="-ms-1" aria-label={m().ui.toggleSidebar} />
			<Separator orientation="vertical" class="h-4" />
			<p class="truncate font-medium text-ink"><bdi>{title}</bdi></p>

			<div class="ms-auto flex items-center gap-1">
				<Button href="/" variant="ghost" size="sm" class="hidden sm:inline-flex">
					{m().nav.home}<ArrowUpRightIcon class="rtl-flip" data-icon="inline-end" />
				</Button>
				<PrefToggles show="language" />
				<div class="hidden sm:contents"><PrefToggles show="theme" /></div>
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
