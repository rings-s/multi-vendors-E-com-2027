import { expect, test } from '@playwright/test';
import { go } from './helpers';

/** vite-pwa: the app is installable from any page and serves every manifest icon. */
test('the app is installable with the brand icons', async ({ page, context }) => {
	for (const path of ['/', '/stores']) {
		await go(page, path);
		// Absolute, so it resolves the same on nested routes.
		await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
			'href',
			'/manifest.webmanifest'
		);

		const cdp = await context.newCDPSession(page);
		const { url, errors, data } = await cdp.send('Page.getAppManifest');
		expect(new URL(url).pathname).toBe('/manifest.webmanifest');
		expect(errors).toEqual([]);
		const { installabilityErrors } = await cdp.send('Page.getInstallabilityErrors');
		expect(installabilityErrors).toEqual([]);

		const manifest = JSON.parse(data ?? '{}') as {
			icons: { src: string; sizes: string; purpose?: string }[];
		};
		expect(manifest.icons.map((i) => i.sizes)).toEqual(
			expect.arrayContaining(['192x192', '512x512'])
		);
		expect(manifest.icons.some((i) => i.purpose === 'maskable')).toBe(true);
		for (const icon of manifest.icons) {
			const res = await page.request.get(icon.src);
			expect(res.status(), icon.src).toBe(200);
			expect(res.headers()['content-type']).toBe('image/png');
		}
	}

	const sw = await page.evaluate(
		async () => (await navigator.serviceWorker.ready).active?.scriptURL ?? null
	);
	expect(sw).toMatch(/\/sw\.js$/);

	for (const href of ['/favicon.ico', '/favicon.svg', '/apple-touch-icon-180x180.png']) {
		// Svelte may write the URL out in full after hydration; match on the path.
		await expect(page.locator(`head link[href$="${href}"]`)).toHaveCount(1);
		expect((await page.request.get(href)).status(), href).toBe(200);
	}
});
