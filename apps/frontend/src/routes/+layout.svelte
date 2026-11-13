<script lang="ts">
	import './layout.css';
	import '@fontsource/ibm-plex-sans-arabic/400.css';
	import '@fontsource/ibm-plex-sans-arabic/500.css';
	import '@fontsource/ibm-plex-sans-arabic/600.css';
	import '@fontsource-variable/inter/opsz.css';
	import { goto, onNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { pwaInfo } from 'virtual:pwa-info';
	import { setSessionExpiredHandler } from '#lib/api/client.js';
	import ConfirmHost from '#lib/components/app/ConfirmHost.svelte';
	import NavProgress from '#lib/components/app/NavProgress.svelte';
	import { Toaster } from '#lib/components/ui/sonner/index.js';
	import { dir, locale, m } from '#lib/i18n/state.svelte.js';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();

	// Keep <html> in sync after client-side language/theme changes (SSR sets them initially).
	$effect(() => {
		document.documentElement.lang = locale();
		document.documentElement.dir = dir();
		document.documentElement.dataset.theme = data.theme;
	});

	// Lets end-to-end tests wait until the app is interactive.
	onMount(() => {
		document.body.dataset.hydrated = 'true';
	});

	// Service worker (vite-pwa): makes the app installable and precaches the hashed build
	// assets. Pages always come from the network, so a new worker never needs a forced reload;
	// the next navigation simply picks up the new version.
	onMount(() => {
		if (!pwaInfo) return;
		void import('virtual:pwa-register').then(({ registerSW }) =>
			registerSW({ immediate: true, onNeedReload: () => {} })
		);
	});

	// Page changes cross-fade (and a product image travels from card to page). Query-only
	// changes such as filters and pagination stay instant.
	onNavigate((navigation) => {
		if (!document.startViewTransition) return;
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		if (navigation.from?.url.pathname === navigation.to?.url.pathname) return;
		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});

	setSessionExpiredHandler(() => {
		toast.error(m().auth.sessionExpired);
		void goto(`/sign-in?next=${encodeURIComponent(page.url.pathname + page.url.search)}`, {
			invalidateAll: true
		});
	});
</script>

<svelte:head>
	<!-- Icons generated from static/favicon.svg by `pnpm pwa:assets` (pwa-assets.config.ts). -->
	<link rel="icon" href="/favicon.ico" sizes="48x48" />
	<link rel="icon" href="/favicon.svg" sizes="any" type="image/svg+xml" />
	<link rel="apple-touch-icon" href="/apple-touch-icon-180x180.png" />
	{#if pwaInfo}
		<link
			rel="manifest"
			href={pwaInfo.webManifest.href}
			crossorigin={pwaInfo.webManifest.useCredentials ? 'use-credentials' : undefined}
		/>
	{/if}
	<meta name="description" content={m().brand.tagline} />
</svelte:head>

<a
	href="#main"
	class="sr-only z-[70] rounded-md bg-primary px-4 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:start-4 focus:top-4"
>
	{m().common.skipToContent}
</a>
<NavProgress />
{@render children()}
<ConfirmHost />
<Toaster
	theme={data.theme}
	position={dir() === 'rtl' ? 'bottom-left' : 'bottom-right'}
	dir={dir()}
	richColors
	closeButton
/>
