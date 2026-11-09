<script lang="ts">
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import InfoIcon from '@lucide/svelte/icons/info';
	import RecordForm from '#lib/components/app/data/RecordForm.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { dataUrl, modelLabel, noteText } from '#lib/data-admin.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().data);
	const model = $derived(modelLabel(t, data.schema.key));
</script>

<svelte:head><title>{t.addRecord} · {model} · {t.title}</title></svelte:head>

<div class="flex max-w-3xl flex-col gap-6">
	<PageHeader title={t.addRecord} eyebrow={model}>
		{#snippet actions()}
			<Button variant="ghost" href={dataUrl(data.schema.key)}
				><ArrowLeftIcon data-icon="inline-start" class="rtl:rotate-180" />{model}</Button
			>
		{/snippet}
	</PageHeader>
	{#each data.schema.notes as note (note)}
		<Alert.Root variant={note === 'financial' ? 'warning' : 'default'}>
			<InfoIcon />
			<Alert.Description>{noteText(t, note)}</Alert.Description>
		</Alert.Root>
	{/each}
	{#key data.schema.key}
		<RecordForm schema={data.schema} row={null} initial={data.initial} />
	{/key}
</div>
