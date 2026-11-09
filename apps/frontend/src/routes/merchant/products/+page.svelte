<script lang="ts">
	import { goto, invalidate } from '$app/navigation';
	import ArchiveIcon from '@lucide/svelte/icons/archive';
	import PackageIcon from '@lucide/svelte/icons/package';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { api, call } from '#lib/api/client.js';
	import type { Product } from '#lib/api/types.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import Picture from '#lib/components/app/Picture.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	async function archive(p: Product) {
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
					api.DELETE('/api/v1/merchant/products/{product_id}', {
						params: { path: { product_id: p.id } }
					})
				),
			m().common.saved
		);
		await invalidate('app:products');
	}
</script>

<svelte:head><title>{m().merchant.products} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().merchant.products}>
		{#snippet actions()}<Button href="/merchant/products/new" data-testid="new-product"
				><PlusIcon data-icon="inline-start" />{m().merchant.newProduct}</Button
			>{/snippet}
	</PageHeader>

	<FilterBar>
		<Field.Field class="min-w-52 flex-1">
			<Field.Label for="pf-q">{m().common.search}</Field.Label>
			<Input id="pf-q" name="q" type="search" value={data.filters.q} />
		</Field.Field>
		<Field.Field class="w-auto">
			<Field.Label for="pf-status">{m().common.status}</Field.Label>
			<NativeSelect.Root id="pf-status" name="status" value={data.filters.status}>
				<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
				{#each ['DRAFT', 'ACTIVE', 'ARCHIVED', 'BLOCKED'] as s (s)}<NativeSelect.Option value={s}
						>{statusLabel(s)}</NativeSelect.Option
					>{/each}
			</NativeSelect.Root>
		</Field.Field>
	</FilterBar>

	{#if data.products.items.length}
		<div class="overflow-hidden rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().merchant.productTitle}</Table.Head>
						<Table.Head>{m().catalog.sku}</Table.Head>
						<Table.Head class="text-end">{m().merchant.price}</Table.Head>
						<Table.Head class="text-end">{m().merchant.available}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
						<Table.Head class="text-end"
							><span class="sr-only">{m().common.actions}</span></Table.Head
						>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.products.items as p (p.id)}
						<Table.Row class="cursor-pointer" onclick={() => goto(`/merchant/products/${p.id}`)}>
							<Table.Cell>
								<div class="flex items-center gap-3">
									<div class="size-10 shrink-0 overflow-hidden rounded-md bg-surface-2">
										<Picture src={p.images[0]?.url} alt="" fallback={p.title} />
									</div>
									<div class="min-w-0">
										<a
											href="/merchant/products/{p.id}"
											class="block max-w-64 truncate font-medium hover:underline"
											onclick={(e) => e.stopPropagation()}>{p.title}</a
										>
										{#if p.variants.length}<p class="text-xs text-ink-3">
												{m().merchant.variants}: {fmt.number(p.variants.length)}
											</p>{/if}
									</div>
								</div>
							</Table.Cell>
							<Table.Cell class="text-ink-2" dir="ltr">{p.sku}</Table.Cell>
							<Table.Cell class="text-end tabular"
								>{fmt.money(p.discounted_price ?? p.price)}</Table.Cell
							>
							<Table.Cell
								class={cn('text-end tabular', p.available_quantity === 0 && 'text-danger')}
								>{fmt.number(p.available_quantity)}</Table.Cell
							>
							<Table.Cell><StatusBadge status={p.status} /></Table.Cell>
							<Table.Cell class="text-end">
								<div class="flex justify-end gap-1">
									<Button
										size="icon-sm"
										variant="ghost"
										href="/merchant/products/{p.id}"
										aria-label="{m().common.edit}: {p.title}"
										onclick={(e) => e.stopPropagation()}><PencilIcon /></Button
									>
									{#if p.status !== 'ARCHIVED'}
										<Button
											size="icon-sm"
											variant="ghost"
											aria-label="{m().merchant.archive}: {p.title}"
											onclick={(e) => {
												e.stopPropagation();
												archive(p);
											}}><ArchiveIcon /></Button
										>
									{/if}
								</div>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator
			total={data.products.total}
			page={data.products.page}
			pageSize={data.products.page_size}
		/>
	{:else}
		<EmptyState icon={PackageIcon} title={m().merchant.noProducts}>
			<Button href="/merchant/products/new"
				><PlusIcon data-icon="inline-start" />{m().merchant.newProduct}</Button
			>
		</EmptyState>
	{/if}
</div>
