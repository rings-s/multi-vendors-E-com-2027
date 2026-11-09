import { expect, test } from '@playwright/test';
import {
	addProductToCart,
	CUSTOMER_STATE,
	emptyCart,
	go,
	expectDirection,
	messages,
	payOnMockProvider,
	placeOrder,
	setLanguage,
	type Lang
} from './helpers';

test.use({ storageState: CUSTOMER_STATE });

for (const lang of ['en', 'ar'] as Lang[]) {
	test.describe(`checkout (${lang === 'ar' ? 'Arabic, RTL' : 'English, LTR'})`, () => {
		test.beforeEach(async ({ context, baseURL }) => {
			await setLanguage(context, baseURL!, lang);
		});

		test('customer buys a product and pays the store through the mock provider', async ({
			page,
			baseURL
		}) => {
			const t = messages[lang];
			await emptyCart(page, lang);
			await addProductToCart(page, lang);

			// Cart shows server-calculated totals grouped by store.
			await go(page, '/cart');
			await expectDirection(page, lang);
			await expect(page.getByTestId('cart-group')).toHaveCount(1);
			await expect(page.getByTestId('order-total')).toContainText(lang === 'ar' ? 'ر.س' : 'SAR');

			await placeOrder(page, lang);
			await expect(
				page.getByRole('heading', { level: 1, name: t.checkout.payTitle })
			).toBeVisible();
			await expect(page.getByTestId('test-mode')).toBeVisible();
			await expect(page.getByTestId('pay-row')).toHaveCount(1);

			await page.getByTestId('pay-store').click();
			await payOnMockProvider(page, baseURL!, 'approve');

			// The result page verifies the payment with the backend before showing it.
			const result = page.getByTestId('payment-result');
			await expect(result).toHaveAttribute('data-outcome', 'paid', { timeout: 20_000 });
			await expectDirection(page, lang);
			await expect(page.getByRole('heading', { name: t.checkout.resultPaid })).toBeVisible();

			await page.getByTestId('view-order').click();
			await expect(page).toHaveURL(/\/account\/orders\/[0-9a-f-]{36}$/);
			const storeOrder = page.getByTestId('merchant-order');
			await expect(storeOrder.locator('[data-status="PAID"]').first()).toBeVisible();
			await expect(storeOrder.getByRole('link', { name: t.orders.receipt })).toBeVisible();

			// The order is listed in the customer's order history.
			await go(page, '/account/orders');
			await expect(page.getByTestId('order-row').first()).toBeVisible();
		});
	});
}

test('a declined payment can be retried and then completed', async ({ page, context, baseURL }) => {
	const lang: Lang = 'en';
	const t = messages[lang];
	await setLanguage(context, baseURL!, lang);
	await emptyCart(page, lang);
	await addProductToCart(page, lang);
	await placeOrder(page, lang);

	await page.getByTestId('pay-store').click();
	await payOnMockProvider(page, baseURL!, 'decline');
	await expect(page.getByTestId('payment-result')).toHaveAttribute('data-outcome', 'failed', {
		timeout: 20_000
	});
	await expect(page.getByRole('heading', { name: t.checkout.resultFailed })).toBeVisible();

	// The unpaid store order is offered again with a retry action.
	const retry = page.getByTestId('pay-store');
	await expect(retry).toHaveText(new RegExp(t.checkout.retryPayment));
	await retry.click();
	await payOnMockProvider(page, baseURL!, 'approve');
	await expect(page.getByTestId('payment-result')).toHaveAttribute('data-outcome', 'paid', {
		timeout: 20_000
	});
});

test('signed-out visitors are sent to sign in before checkout', async ({ browser, baseURL }) => {
	// Explicitly signed out: contexts created in a test inherit `test.use` options.
	const context = await browser.newContext({
		baseURL,
		locale: 'en-US',
		storageState: { cookies: [], origins: [] }
	});
	const page = await context.newPage();
	await go(page, '/checkout');
	await expect(page).toHaveURL(/\/sign-in\?next=%2Fcheckout$/);
	await context.close();
});
