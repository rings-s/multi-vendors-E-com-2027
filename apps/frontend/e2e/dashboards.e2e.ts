import { expect, test, type Browser } from '@playwright/test';
import { go, messages, setLanguage, type Lang } from './helpers';

/** Demo accounts created by `seed-dev`. */
const ACCOUNTS = {
	admin: { email: 'admin@example.com', path: '/admin', figures: 6 },
	merchant: { email: 'merchant@example.com', path: '/merchant', figures: 5 }
} as const;
const PASSWORD = 'demo-password-123';

async function signIn(browser: Browser, baseURL: string, email: string, lang: Lang) {
	const t = messages[lang];
	const context = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
	await setLanguage(context, baseURL, lang);
	const page = await context.newPage();
	await go(page, '/sign-in');
	await page.getByLabel(t.auth.email).fill(email);
	await page.getByLabel(t.auth.password).fill(PASSWORD);
	await page.getByRole('button', { name: t.auth.signIn, exact: true }).click();
	await expect(page).not.toHaveURL(/sign-in/);
	return { context, page };
}

for (const [role, account] of Object.entries(ACCOUNTS)) {
	for (const lang of ['en', 'ar'] as const) {
		test(`${role} dashboard charts render and follow the period filter (${lang})`, async ({
			browser,
			baseURL
		}) => {
			const t = messages[lang];
			const { context, page } = await signIn(browser, baseURL!, account.email, lang);
			const errors: string[] = [];
			page.on('pageerror', (e) => errors.push(String(e)));
			page.on('console', (msg) => msg.type() === 'error' && errors.push(msg.text()));

			await go(page, account.path);
			const analytics = page.getByTestId('analytics');
			await expect(analytics.getByRole('heading', { name: t.analytics.title })).toBeVisible();
			await expect(analytics.getByText(t.analytics.description({ n: 30 }))).toBeVisible();

			// Every chart shows either a drawn canvas or its empty state, never nothing.
			const figures = analytics.locator('figure');
			await expect(figures).toHaveCount(account.figures);
			for (const figure of await figures.all()) {
				const canvas = figure.locator('canvas');
				if (await canvas.count()) {
					const size = await canvas.evaluate((c: HTMLCanvasElement) => c.width * c.height);
					expect(size).toBeGreaterThan(0);
				} else {
					await expect(figure.locator('[data-slot=empty]')).toBeVisible();
				}
			}

			// One filter above everything it scopes: picking 7 days re-scopes the charts.
			await analytics.getByRole('radio', { name: t.merchant.days({ n: 7 }) }).click();
			await expect(page).toHaveURL(/[?&]days=7\b/);
			await expect(analytics.getByText(t.analytics.description({ n: 7 }))).toBeVisible();
			await expect(figures).toHaveCount(account.figures);

			expect(errors).toEqual([]);
			await context.close();
		});
	}
}
