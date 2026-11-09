import { expect, type BrowserContext, type Page } from '@playwright/test';
import ar from '../src/lib/i18n/messages/ar';
import en from '../src/lib/i18n/messages/en';

export type Lang = 'ar' | 'en';
export const messages = { ar, en } as const;

/** Demo accounts created by `python -m app.cli seed-dev`. */
export const CUSTOMER = { email: 'customer@example.com', password: 'demo-password-123' };
export const STORE_SLUG = 'najd-oud';
/** A seeded product with plenty of stock and no variants. */
export const PRODUCT_TITLE = 'Bakhoor Gift Box';

export const CUSTOMER_STATE = 'e2e/.auth/customer.json';

/** Navigate and wait until the SvelteKit app has hydrated (forms are interactive). */
export async function go(page: Page, path: string) {
	await page.goto(path);
	await hydrated(page);
}

export async function hydrated(page: Page) {
	await page.locator('body[data-hydrated="true"]').waitFor({ state: 'attached' });
}

export async function setLanguage(context: BrowserContext, baseURL: string, lang: Lang) {
	await context.addCookies([{ name: 'lang', value: lang, url: baseURL }]);
}

export async function expectDirection(page: Page, lang: Lang) {
	await expect(page.locator('html')).toHaveAttribute('lang', lang);
	await expect(page.locator('html')).toHaveAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
}

/** Empty the server-side cart through the UI so each test starts clean. */
export async function emptyCart(page: Page, lang: Lang) {
	const t = messages[lang];
	await go(page, '/cart');
	const clear = page.getByRole('button', { name: t.cart.clear });
	if (await clear.isVisible()) {
		await clear.click();
		await page.getByRole('alertdialog').getByRole('button', { name: t.cart.clear }).click();
	}
	await expect(page.getByRole('heading', { name: t.cart.empty })).toBeVisible();
}

export async function addProductToCart(page: Page, lang: Lang) {
	const t = messages[lang];
	await go(page, `/stores/${STORE_SLUG}`);
	await page.getByTestId('product-card').filter({ hasText: PRODUCT_TITLE }).click();
	await expect(page.getByRole('heading', { level: 1, name: PRODUCT_TITLE })).toBeVisible();
	await page.getByTestId('add-to-cart').click();
	await expect(page.getByText(t.catalog.added)).toBeVisible();
	await expect(page.getByTestId('cart-count')).toBeVisible();
}

/** Fill in whatever the checkout form still needs, accept the terms and place the order. */
export async function placeOrder(page: Page, lang: Lang) {
	const t = messages[lang];
	await go(page, '/cart');
	await page.getByTestId('go-checkout').click();
	await expect(page).toHaveURL(/\/checkout$/);
	await expect(page.getByRole('heading', { level: 1, name: t.checkout.title })).toBeVisible();

	const phone = page.locator('#c-phone');
	if (!(await phone.inputValue())) await phone.fill('0512345678');

	// First checkout for this customer: the new-address form opens automatically.
	if (await page.locator('#na-recipient').isVisible()) {
		await page.locator('#na-recipient').fill('Sara Customer');
		await page.locator('#na-phone').fill('0512345678');
		await page.locator('#na-region').selectOption('riyadh');
		await page.locator('#na-city').fill('Riyadh');
		await page.getByRole('button', { name: t.common.save, exact: true }).click();
		await expect(page.locator('#na-recipient')).toBeHidden();
	}

	await page.locator('#terms').click();
	await page.getByTestId('place-order').click();
	await expect(page).toHaveURL(/\/checkout\/pay\/[0-9a-f-]{36}$/);
}

/**
 * Pay on the mock provider's hosted page. The provider redirects to the backend's
 * `FRONTEND_URL`; if that differs from the test server, continue on the test server.
 */
export async function payOnMockProvider(
	page: Page,
	baseURL: string,
	outcome: 'approve' | 'decline'
) {
	await expect(page).toHaveURL(/\/api\/v1\/mock-provider\/payments\/.+\/checkout/);
	await expect(page.getByText('TEST MODE')).toBeVisible();
	await page
		.getByRole('button', { name: outcome === 'approve' ? 'Approve payment' : 'Decline payment' })
		.click();
	await page.waitForURL(/\/checkout\/result\?/);
	const url = new URL(page.url());
	if (url.origin !== new URL(baseURL).origin) await page.goto(url.pathname + url.search);
	await hydrated(page);
}
