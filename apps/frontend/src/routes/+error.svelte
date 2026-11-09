<script lang="ts">
	import { page } from '$app/state';
	import * as Empty from '#lib/components/ui/empty/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { m } from '#lib/i18n/state.svelte.js';

	const status = $derived(page.status);
	const copy = $derived(
		status === 404
			? { title: m().errors.notFoundTitle, body: m().errors.notFoundBody }
			: status === 403
				? { title: m().errors.forbiddenTitle, body: m().errors.forbiddenBody }
				: { title: m().errors.serverTitle, body: m().errors.serverBody }
	);
</script>

<svelte:head><title>{copy.title} · {m().brand.name}</title></svelte:head>

<main id="main" class="container-page grid min-h-[70dvh] place-items-center py-24">
	<Empty.Root class="max-w-md">
		<Empty.Header class="max-w-md">
			<p class="font-display text-7xl text-ink-3/60 tabular">{status}</p>
			<h1 class="font-display text-3xl text-ink">{copy.title}</h1>
			<Empty.Description>{copy.body}</Empty.Description>
		</Empty.Header>
		<Empty.Content class="flex-row justify-center">
			<Button href="/">{m().errors.goHome}</Button>
			{#if status >= 500}
				<Button variant="outline" onclick={() => location.reload()}>{m().common.retry}</Button>
			{/if}
		</Empty.Content>
	</Empty.Root>
</main>
