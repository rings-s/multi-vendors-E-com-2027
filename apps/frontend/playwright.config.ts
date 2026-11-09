import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests against a real backend running the mock payment provider.
 *
 * - `API_URL` points the frontend at the backend (default http://localhost:8000).
 * - `E2E_PORT` is the frontend port. It should match the backend's `FRONTEND_URL`
 *   (default http://localhost:5173), because the mock provider redirects the payer
 *   back to `FRONTEND_URL/checkout/result`.
 * - An already-running server on that port (e.g. `pnpm dev`) is reused.
 * - The backend must contain the `seed-dev` demo data.
 */
const PORT = Number(process.env.E2E_PORT ?? 5173);
const baseURL = `http://localhost:${PORT}`;

export default defineConfig({
	testDir: 'e2e',
	// The tests share one backend (cart, stock), so they run one at a time.
	fullyParallel: false,
	workers: 1,
	timeout: 60_000,
	expect: { timeout: 10_000 },
	retries: process.env.CI ? 1 : 0,
	reporter: process.env.CI ? 'github' : 'list',
	use: {
		baseURL,
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure'
	},
	projects: [
		{ name: 'setup', testMatch: /.*\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: /.*\.e2e\.ts/,
			dependencies: ['setup'],
			use: { ...devices['Desktop Chrome'] }
		}
	],
	webServer: {
		command: `pnpm build && pnpm preview --port ${PORT} --strictPort`,
		url: baseURL,
		reuseExistingServer: true,
		timeout: 240_000,
		env: { API_URL: process.env.API_URL ?? 'http://localhost:8000' }
	}
});
