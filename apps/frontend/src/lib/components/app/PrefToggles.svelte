<script lang="ts">
	import { page } from '$app/state';
	import MonitorIcon from '@lucide/svelte/icons/monitor';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import SunIcon from '@lucide/svelte/icons/sun';
	import { locale, m } from '#lib/i18n/state.svelte.js';
	import type { Locale } from '#lib/i18n/index.js';
	import { setLocale, setTheme, type Theme } from '#lib/prefs.js';
	import Segmented from './Segmented.svelte';

	/** Language and theme toggles, shared by the storefront header, its menu and the dashboards. */
	interface Props {
		show?: 'both' | 'language' | 'theme';
		/** Full-width segments with text labels (menus). */
		expanded?: boolean;
		/** Expose the language test hook. Only one instance per page may. */
		testable?: boolean;
		class?: string;
	}
	let { show = 'both', expanded = false, testable = true, class: className }: Props = $props();

	const user = $derived(page.data.user);
	const theme = $derived((page.data.theme ?? 'system') as Theme);
	const languages = $derived([
		{
			value: 'en' as Locale,
			label: expanded ? 'English' : 'EN',
			lang: 'en',
			testid: testable && locale() !== 'en' ? 'locale-switch' : undefined
		},
		{
			value: 'ar' as Locale,
			label: expanded ? 'العربية' : 'عربي',
			lang: 'ar',
			testid: testable && locale() !== 'ar' ? 'locale-switch' : undefined
		}
	]);
	const themes = $derived([
		{ value: 'light' as Theme, label: m().common.themeLight, icon: SunIcon },
		{ value: 'dark' as Theme, label: m().common.themeDark, icon: MoonIcon },
		{ value: 'system' as Theme, label: m().common.themeSystem, icon: MonitorIcon }
	]);
</script>

{#if show !== 'theme'}
	<Segmented
		value={locale()}
		options={languages}
		label={m().common.language}
		onchange={(v) => setLocale(v, !!user)}
		fill={expanded}
		size={expanded ? 'md' : 'sm'}
		class={className}
	/>
{/if}
{#if show !== 'language'}
	<Segmented
		value={theme}
		options={themes}
		label={m().common.theme}
		onchange={setTheme}
		iconOnly={!expanded}
		fill={expanded}
		size={expanded ? 'md' : 'sm'}
		class={className}
	/>
{/if}
