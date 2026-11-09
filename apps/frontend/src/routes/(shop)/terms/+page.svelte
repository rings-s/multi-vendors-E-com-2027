<script lang="ts">
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import { m } from '#lib/i18n/state.svelte.js';
</script>

<svelte:head><title>{m().legal.termsTitle} · {m().brand.name}</title></svelte:head>

<article class="container-page flex max-w-3xl flex-col gap-6 py-14">
	<PageHeader title={m().legal.termsTitle} />
	<div class="flex flex-col gap-4 leading-relaxed text-ink-2">
		<p>{m().legal.terms1}</p>
		<p>{m().legal.terms2}</p>
		<p>{m().legal.terms3}</p>
	</div>
</article>
