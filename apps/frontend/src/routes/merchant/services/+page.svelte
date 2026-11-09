<script lang="ts">
	import { goto, invalidate } from '$app/navigation';
	import ArchiveIcon from '@lucide/svelte/icons/archive';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import { api, call } from '#lib/api/client.js';
	import type { Service } from '#lib/api/types.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import Picture from '#lib/components/app/Picture.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	async function archive(s: Service) {
		if (
			!(await confirm({
				title: m().merchant.archive,
				description: m().merchant.archiveConfirm,
				destructive: true,
				confirmLabel: m().merchant.archive
			}))
		)
			return;
		await action(
			() =>
				call(
					api.DELETE('/api/v1/merchant/services/{service_id}', {
						params: { path: { service_id: s.id } }
					})
				),
			m().common.saved
		);
		await invalidate('app:services');
	}
</script>

<svelte:head><title>{m().merchant.services} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.services}>
		{#snippet actions()}<Button href="/merchant/services/new"
				><PlusIcon data-icon="inline-start" />{m().merchant.newService}</Button
			>{/snippet}
	</PageHeader>
	{#if data.services.items.length}
		<div class="overflow-hidden rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().merchant.productTitle}</Table.Head>
						<Table.Head>{m().catalog.duration}</Table.Head>
						<Table.Head>{m().merchant.locationType}</Table.Head>
						<Table.Head class="text-end">{m().merchant.price}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
						<Table.Head class="text-end"
							><span class="sr-only">{m().common.actions}</span></Table.Head
						>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.services.items as s (s.id)}
						<Table.Row class="cursor-pointer" onclick={() => goto(`/merchant/services/${s.id}`)}>
							<Table.Cell>
								<div class="flex items-center gap-3">
									<div class="size-10 shrink-0 overflow-hidden rounded-md bg-surface-2">
										<Picture src={s.images[0]?.url} alt="" fallback={s.title} />
									</div>
									<a
										href="/merchant/services/{s.id}"
										class="max-w-64 truncate font-medium hover:underline"
										onclick={(e) => e.stopPropagation()}>{s.title}</a
									>
								</div>
							</Table.Cell>
							<Table.Cell class="tabular"
								>{m().common.minutes({ n: s.duration_minutes })}</Table.Cell
							>
							<Table.Cell class="text-ink-2">{statusLabel(s.location_type)}</Table.Cell>
							<Table.Cell class="text-end tabular"
								>{fmt.money(s.discounted_price ?? s.price)}</Table.Cell
							>
							<Table.Cell
								><div class="flex gap-1.5">
									<StatusBadge status={s.status} />{#if s.availability !== 'AVAILABLE'}<StatusBadge
											status={s.availability}
										/>{/if}
								</div></Table.Cell
							>
							<Table.Cell class="text-end">
								<div class="flex justify-end gap-1">
									<Button
										size="icon-sm"
										variant="ghost"
										href="/merchant/services/{s.id}"
										aria-label="{m().common.edit}: {s.title}"
										onclick={(e) => e.stopPropagation()}><PencilIcon /></Button
									>
									{#if s.status !== 'ARCHIVED'}<Button
											size="icon-sm"
											variant="ghost"
											aria-label="{m().merchant.archive}: {s.title}"
											onclick={(e) => {
												e.stopPropagation();
												archive(s);
											}}><ArchiveIcon /></Button
										>{/if}
								</div>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={data.services.total}
			page={data.services.page}
			pageSize={data.services.page_size}
		/>
	{:else}
		<EmptyState icon={SparklesIcon} title={m().merchant.noServices}>
			<Button href="/merchant/services/new"
				><PlusIcon data-icon="inline-start" />{m().merchant.newService}</Button
			>
		</EmptyState>
	{/if}
</div>
