import { expect, test as setup } from '@playwright/test';
import { CUSTOMER, CUSTOMER_STATE, go, messages, setLanguage } from './helpers';

/**
 * Sign in once through the real sign-in form and reuse the session in the
 * checkout tests (the backend rate-limits authentication endpoints).
 */
setup('customer signs in with the sign-in form', async ({ page, context, baseURL }) => {
	const t = messages.en;
	await setLanguage(context, baseURL!, 'en');
	await go(page, '/sign-in');
	await expect(page.getByRole('heading', { name: t.auth.signInTitle })).toBeVisible();

	// Wrong password: the translated error is shown and the user stays on the page.
	await page.getByLabel(t.auth.email).fill(CUSTOMER.email);
	await page.getByLabel(t.auth.password).fill('not-the-password');
	await page.getByRole('button', { name: t.auth.signIn, exact: true }).click();
	await expect(page.getByTestId('form-error')).toHaveText(t.errors.codes.invalid_credentials);

	await page.getByLabel(t.auth.password).fill(CUSTOMER.password);
	await page.getByRole('button', { name: t.auth.signIn, exact: true }).click();
	await expect(page).toHaveURL(/\/account$/);
	await expect(page.getByRole('heading', { level: 1 })).toContainText('Hello');

	await page.context().storageState({ path: CUSTOMER_STATE });
});
