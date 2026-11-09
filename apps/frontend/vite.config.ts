import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-auto';
import { withPwa } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		// `withPwa` runs the `sveltekit()` plugin itself (first argument: its options) and adds
		// the web manifest, the generated icons (pwa-assets.config.ts) and the service worker.
		withPwa(
			{
				compilerOptions: {
					// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
					runes: ({ filename }) =>
						filename.split(/[/\\]/).includes('node_modules') ? undefined : true
				},

				// adapter-auto only supports some environments, see https://svelte.dev/docs/kit/adapter-auto for a list.
				// If your environment is not supported, or you settled on a specific environment, switch out the adapter.
				// See https://svelte.dev/docs/kit/adapters for more information about adapters.
				adapter: adapter()
			},
			{
				// The service worker is registered from the root layout (virtual:pwa-register).
				// The app is served from the domain root. SvelteKit's relative base would make the
				// manifest link resolve per page (/stores/manifest.webmanifest on /stores/x).
				base: '/',
				injectRegister: false,
				registerType: 'autoUpdate',
				// Icons are generated into static/ by `pnpm pwa:assets` (pwa-assets.config.ts). The
				// integrated generator only injects manifest entries and never writes the files in a
				// SvelteKit build, so it stays off.
				pwaAssets: { disabled: true },
				manifest: {
					id: '/',
					name: 'سوق كولكتيف · Souq Collective',
					short_name: 'سوق كولكتيف',
					description:
						'متاجر سعودية مستقلة في سوق واحد · Independent Saudi stores, one marketplace',
					lang: 'ar',
					dir: 'rtl',
					start_url: '/',
					scope: '/',
					display: 'standalone',
					orientation: 'portrait',
					background_color: '#ffffff',
					theme_color: '#ffffff',
					categories: ['shopping', 'business'],
					icons: [
						{ src: '/pwa-64x64.png', sizes: '64x64', type: 'image/png' },
						{ src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' },
						{ src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png' },
						{
							src: '/maskable-icon-512x512.png',
							sizes: '512x512',
							type: 'image/png',
							purpose: 'maskable'
						}
					]
				},
				generateSW: {
					// Pages are server-rendered per user (session, language, cart): never answer a
					// navigation from the cache.
					navigateFallback: null,
					cleanupOutdatedCaches: true,
					// Precache only the app icons and manifest, so a first visit downloads almost
					// nothing extra. Hashed build files (JS, CSS, fonts) are cached as they are used.
					globPatterns: ['client/*.{ico,png,svg,webmanifest}'],
					// No route is prerendered, so the plugin's added `prerendered/**` glob is empty.
					globStrict: false,
					runtimeCaching: [
						{
							urlPattern: /\/_app\/immutable\//,
							handler: 'CacheFirst',
							options: {
								cacheName: 'app-immutable',
								expiration: { maxEntries: 500, maxAgeSeconds: 60 * 60 * 24 * 60 }
							}
						}
					]
				},
				devOptions: { enabled: true, suppressWarnings: true, navigateFallback: undefined }
			}
		)
	]
});
