<script lang="ts">
	import type { Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import SlidersHorizontalIcon from '@lucide/svelte/icons/sliders-horizontal';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { m } from '#lib/i18n/state.svelte.js';

	/**
	 * A GET form whose fields map to URL query parameters, so filtered views are
	 * shareable and work without JavaScript. Changing a select applies immediately.
	 */
	let { children, label }: { children: Snippet; label?: string } = $props();

	function submit(e: SubmitEvent) {
		e.preventDefault();
		apply(e.currentTarget as HTMLFormElement);
	}

	function apply(form: HTMLFormElement) {
		const url = new URL(page.url.pathname, page.url.origin);
		for (const [k, v] of new FormData(form)) {
			if (typeof v === 'string' && v.trim()) url.searchParams.set(k, v.trim());
		}
		void goto(url);
	}

	function onchange(e: Event) {
		const t = e.target as HTMLElement;
		if (t instanceof HTMLSelectElement) apply(t.form!);
	}

	const hasFilters = $derived(
		[...page.url.searchParams.keys()].some((k) => k !== 'page' && k !== 'sort')
	);
</script>

<Card.Root size="sm" class="py-3 sm:py-4">
	<Card.Content class="px-3 sm:px-4">
		<form
			method="GET"
			class="flex flex-wrap items-end gap-3"
			onsubmit={submit}
			{onchange}
			aria-label={label ?? m().common.filters}
		>
			{@render children()}
			<div class="flex gap-2">
				<Button type="submit" variant="secondary"
					><SlidersHorizontalIcon data-icon="inline-start" />{m().common.apply}</Button
				>
				{#if hasFilters}
					<Button href={page.url.pathname} variant="ghost">{m().common.reset}</Button>
				{/if}
			</div>
		</form>
	</Card.Content>
</Card.Root>
