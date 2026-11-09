// See https://svelte.dev/docs/kit/types#app.d.ts
/// <reference types="@unplugin-pwa/core/info" />
/// <reference types="@unplugin-pwa/core/vanillajs" />
import type { UserPublic } from '#lib/api/types.js';
import type { Locale } from '#lib/i18n/index.js';

declare global {
	namespace App {
		interface Error {
			message: string;
			code?: string;
		}
		interface Locals {
			user: UserPublic | null;
			locale: Locale;
			theme: 'light' | 'dark' | 'system';
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
