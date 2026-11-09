<script lang="ts">
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import ServiceForm from '#lib/components/app/ServiceForm.svelte';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().merchant.newService} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.newService} />
	<ServiceForm categories={data.categories} />
</div>
