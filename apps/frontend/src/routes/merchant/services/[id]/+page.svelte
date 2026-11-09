<script lang="ts">
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import ServiceForm from '#lib/components/app/ServiceForm.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().merchant.editService} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.editService} description={data.service.title}>
		{#snippet meta()}<StatusBadge status={data.service.status} />{/snippet}
	</PageHeader>
	{#key data.service.id}
		<ServiceForm service={data.service} categories={data.categories} />
	{/key}
</div>
