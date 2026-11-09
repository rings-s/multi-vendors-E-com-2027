import { expect, test } from '@playwright/test';
import {
	expectDirection,
	go,
	hydrated,
	messages,
	PRODUCT_TITLE,
	setLanguage,
	STORE_SLUG,
	type Lang
} from './helpers';

test.describe('language and direction', () => {
	test('Arabic is the default for Arabic browsers and renders right-to-left', async ({
		browser,
		baseURL
	}) => {
		const context = await browser.newContext({ locale: 'ar-SA', baseURL });
		const page = await context.newPage();
		await go(page, '/');
		await expectDirection(page, 'ar');
		const nav = page.getByRole('navigation', { name: messages.ar.ui.mainNav }).first();
		await expect(nav.getByRole('link', { name: messages.ar.nav.stores })).toBeVisible();
		await context.close();
	});

	for (const lang of ['ar', 'en'] as Lang[]) {
		test(`${lang === 'ar' ? 'Arabic (RTL)' : 'English (LTR)'}: layout mirrors and content is localised`, async ({
			page,
			context,
			baseURL
		}) => {
			const t = messages[lang];
			await setLanguage(context, baseURL!, lang);
			await go(page, '/');
			await expectDirection(page, lang);

			// Real RTL layout, not just text alignment: the brand sits on the reading-start side.
			const brand = await page.getByRole('link', { name: t.brand.name }).first().boundingBox();
			const cart = await page.getByTestId('cart-link').boundingBox();
			expect(brand && cart).toBeTruthy();
			if (lang === 'ar') expect(brand!.x).toBeGreaterThan(cart!.x);
			else expect(brand!.x).toBeLessThan(cart!.x);

			await expect(page.getByRole('link', { name: t.home.heroCta })).toBeVisible();
			await expect(page.getByRole('contentinfo')).toContainText(t.footer.becomeMerchant);

			// Storefront: translated tabs and SAR formatting for the locale.
			await go(page, `/stores/${STORE_SLUG}`);
			await expect(
				page.getByRole('link', { name: new RegExp(t.stores.products) }).first()
			).toBeVisible();
			const card = page.getByTestId('product-card').filter({ hasText: PRODUCT_TITLE });
			await expect(card).toContainText(lang === 'ar' ? 'ر.س' : 'SAR');

			// Validation and auth pages are translated too.
			await go(page, '/sign-in');
			await expect(page.getByRole('heading', { name: t.auth.signInTitle })).toBeVisible();
			await expect(page.getByLabel(t.auth.email)).toBeVisible();
		});
	}

	test('switching language updates direction and persists across reloads', async ({
		page,
		context,
		baseURL
	}) => {
		await setLanguage(context, baseURL!, 'en');
		await go(page, '/stores');
		await expectDirection(page, 'en');
		await expect(
			page.getByRole('heading', { level: 1, name: messages.en.stores.title })
		).toBeVisible();

		await page.getByTestId('locale-switch').click();
		await expectDirection(page, 'ar');
		await expect(
			page.getByRole('heading', { level: 1, name: messages.ar.stores.title })
		).toBeVisible();

		await page.reload();
		await hydrated(page);
		await expectDirection(page, 'ar');
		await expect(
			page.getByRole('heading', { level: 1, name: messages.ar.stores.title })
		).toBeVisible();

		await page.getByTestId('locale-switch').click();
		await expectDirection(page, 'en');
	});
});
