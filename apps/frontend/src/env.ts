import { defineEnvVars } from '@sveltejs/kit/env';

/**
 * Environment variables. Only `API_URL` is required by the frontend and it is
 * server-only: the browser never talks to the backend directly. All `/api/v1/*`
 * and `/media/*` requests go through the SvelteKit server (see `hooks.server.ts`),
 * so authentication cookies stay first-party and no provider key ever reaches the client.
 */
export const variables = defineEnvVars({
	API_URL: {
		description: 'Base URL of the FastAPI backend, e.g. http://localhost:8000 (no trailing slash).',
		schema: (value) => {
			const url = (value ?? 'http://localhost:8000').replace(/\/+$/, '');
			if (!/^https?:\/\//.test(url)) throw new Error('API_URL must be an http(s) URL');
			return url;
		}
	}
});
