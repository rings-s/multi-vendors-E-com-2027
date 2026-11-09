/**
 * PWA icon generation (@vite-pwa/assets-generator). Run `pnpm pwa:assets` after changing
 * the logo; it writes favicon.ico and the pwa-, maskable- and apple-touch- PNGs into static/
 * (committed). The manifest entries and head links that use them live in vite.config.ts
 * and src/routes/+layout.svelte.
 *
 * Source: static/favicon.svg, the rounded brand tile (copy of docs/logo/logo-rounded.svg).
 *
 * - transparent (favicon.ico, pwa-64/192/512): the rounded tile as is.
 * - maskable-512 and apple-touch-180: full-bleed black square. The OS applies its own
 *   rounding/mask; the mark sits well inside the 80% maskable safe zone.
 */
import { defineConfig, minimal2023Preset } from '@vite-pwa/assets-generator/config';

const fullBleed = { padding: 0, resizeOptions: { background: '#000000' } };

export default defineConfig({
	headLinkOptions: { preset: '2023' },
	preset: {
		...minimal2023Preset,
		transparent: { ...minimal2023Preset.transparent, padding: 0 },
		maskable: { ...minimal2023Preset.maskable, ...fullBleed },
		apple: { ...minimal2023Preset.apple, ...fullBleed }
	},
	images: ['static/favicon.svg']
});
