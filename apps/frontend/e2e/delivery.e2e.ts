import { expect, test } from '@playwright/test';
import {
	addProductToCart,
	CUSTOMER_STATE,
	emptyCart,
	go,
	messages,
	payOnMockProvider,
	setLanguage
} from './helpers';

const MERCHANT = { email: 'merchant@example.com', password: 'demo-password-123' };

test.use({ storageState: CUSTOMER_STATE });

test('customer chooses pickup and the merchant fulfils it from the dashboard', async ({
	page,
	context,
	browser,
	baseURL
}) => {
	const t = messages.en;
	await setLanguage(context, baseURL!, 'en');
	await emptyCart(page, 'en');
	await addProductToCart(page, 'en');

	// The cart shows how each store delivers.
	await go(page, '/cart');
	await expect(page.getByTestId('cart-delivery')).toBeVisible();

	await page.getByTestId('go-checkout').click();
	await expect(page).toHaveURL(/\/checkout$/);
	const choice = page.getByTestId('delivery-choice');
	await expect(choice.getByText(t.delivery.deliverToAddress)).toBeVisible();
	await choice.getByText(t.delivery.pickupFromStore).click();
	// Pickup needs no address; the backend re-prices the order without a delivery fee.
	await expect(page.getByText(t.checkout.noAddressNeeded)).toBeVisible();
	await expect(page.getByTestId('delivery-fee')).toHaveText(t.cart.free);

	const phone = page.locator('#c-phone');
	if (!(await phone.inputValue())) await phone.fill('0512345678');
	await page.locator('#terms').click();
	await page.getByTestId('place-order').click();
	await expect(page).toHaveURL(/\/checkout\/pay\/[0-9a-f-]{36}$/);
	await page.getByTestId('pay-store').click();
	await payOnMockProvider(page, baseURL!, 'approve');
	await expect(page.getByTestId('payment-result')).toHaveAttribute('data-outcome', 'paid', {
		timeout: 20_000
	});
	await page.getByTestId('view-order').click();
	await expect(page).toHaveURL(/\/account\/orders\/[0-9a-f-]{36}$/);
	const card = page.getByTestId('delivery-card');
	await expect(card).toContainText(t.delivery.pickupFromStore);
	await expect(card).toContainText(t.delivery.statusLabel.PENDING);
	const orderUrl = page.url();

	// The merchant moves the pickup through its statuses from the dashboard.
	const merchantContext = await browser.newContext({
		baseURL,
		storageState: { cookies: [], origins: [] }
	});
	await setLanguage(merchantContext, baseURL!, 'en');
	const merchant = await merchantContext.newPage();
	await go(merchant, '/sign-in');
	await merchant.getByLabel(t.auth.email).fill(MERCHANT.email);
	await merchant.getByLabel(t.auth.password).fill(MERCHANT.password);
	await merchant.getByRole('button', { name: t.auth.signIn, exact: true }).click();
	await expect(merchant).not.toHaveURL(/sign-in/);

	await go(merchant, '/merchant/deliveries');
	await merchant.getByTestId('delivery-row').first().getByRole('link').click();
	await expect(merchant).toHaveURL(/\/merchant\/orders\/[0-9a-f-]{36}$/);
	for (const step of ['CONFIRMED', 'READY_FOR_PICKUP', 'DELIVERED']) {
		await merchant.getByTestId(`delivery-${step}`).click();
		await expect(merchant.getByTestId(`delivery-${step}`)).toBeHidden();
	}
	await expect(merchant.getByTestId('delivery-card')).toContainText(t.delivery.collected);
	await merchantContext.close();

	// The customer sees the delivery timeline.
	await go(page, new URL(orderUrl).pathname);
	await expect(card).toContainText(t.delivery.collected);
	await expect(card).toContainText(t.delivery.statusLabel.READY_FOR_PICKUP);
	await expect(
		page.getByTestId('merchant-order').locator('[data-status="DELIVERED"]').first()
	).toBeVisible();
});

test('merchant configures a delivery zone', async ({ browser, baseURL }) => {
	const t = messages.en;
	const context = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
	await setLanguage(context, baseURL!, 'en');
	const page = await context.newPage();
	await go(page, '/sign-in');
	await page.getByLabel(t.auth.email).fill(MERCHANT.email);
	await page.getByLabel(t.auth.password).fill(MERCHANT.password);
	await page.getByRole('button', { name: t.auth.signIn, exact: true }).click();
	await expect(page).not.toHaveURL(/sign-in/);

	await go(page, '/merchant/delivery');
	const rows = page.getByTestId('zone-row');
	const before = await rows.count();
	await page.getByTestId('add-zone').click();
	const name = `Jeddah ${Date.now() % 100000}`;
	await page.locator('#z-name').fill(name);
	await page.locator('#z-region').selectOption('makkah');
	await page.locator('#z-cities').fill('Jeddah, جدة');
	await page.locator('#z-fee').fill('20');
	await page.locator('#z-threshold').fill('250');
	await page.locator('#z-eta-min').fill('24');
	await page.locator('#z-eta-max').fill('48');
	await page.getByRole('dialog').getByRole('button', { name: t.common.save, exact: true }).click();
	await expect(rows).toHaveCount(before + 1);
	const row = rows.filter({ hasText: name });
	await expect(row).toContainText('جدة');
	await row.getByRole('button', { name: `${t.common.delete}: ${name}` }).click();
	await page.getByRole('alertdialog').getByRole('button', { name: t.common.delete }).click();
	await expect(rows).toHaveCount(before);
	await context.close();
});
