<script lang="ts">
	import { invalidate } from '$app/navigation';
	import BadgeCheckIcon from '@lucide/svelte/icons/badge-check';
	import EllipsisIcon from '@lucide/svelte/icons/ellipsis';
	import StarIcon from '@lucide/svelte/icons/star';
	import { api, call } from '#lib/api/client.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import Picture from '#lib/components/app/Picture.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { prompt } from '#lib/confirm.svelte.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	type Mod = 'block' | 'unblock' | 'feature' | 'unfeature';
	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	const rows = $derived(
		(data.products?.items ?? data.services?.items ?? []).map((x) => ({
			id: x.id,
			title: x.title,
			store: x.store.name,
			image: x.images[0]?.url,
			price: x.discounted_price ?? x.price,
			status: x.status,
			featured: x.is_featured,
			href: data.tab === 'services' ? `/services/${x.id}` : `/products/${x.id}`
		}))
	);
	const paged = $derived(data.products ?? data.services!);

	async function moderate(id: string, act: Mod) {
		let note: string | null = null;
		if (act === 'block') {
			note = await prompt({
				title: t.block,
				label: m().merchant.moderationNote,
				minLength: 3,
				destructive: true,
				confirmLabel: t.block
			});
			if (note == null) return;
		}
		const body = { action: act, note };
		await action<unknown>(
			() =>
				data.tab === 'services'
					? call(
							api.POST('/api/v1/admin/services/{service_id}/moderation', {
								params: { path: { service_id: id } },
								body
							})
						)
					: call(
							api.POST('/api/v1/admin/products/{product_id}/moderation', {
								params: { path: { product_id: id } },
								body
							})
						),
			t.moderated
		);
		await invalidate('app:moderation');
	}
</script>

<svelte:head><title>{t.products} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.products} />
	<Tabs.Root value={data.tab} activationMode="manual">
		<Tabs.List variant="line" aria-label={t.products}>
			{#each [['products', m().nav.products], ['services', m().nav.services]] as [key, label] (key)}
				<Tabs.Trigger value={key}>
					{#snippet child({ props })}
						<a
							{...props}
							href={key === 'products' ? '?' : '?tab=services'}
							aria-current={data.tab === key ? 'page' : undefined}>{label}</a
						>
					{/snippet}
				</Tabs.Trigger>
			{/each}
		</Tabs.List>
	</Tabs.Root>
	<FilterBar>
		{#if data.tab === 'services'}<input type="hidden" name="tab" value="services" />{/if}
		<Field.Field class="min-w-52 flex-1">
			<Field.Label for="mp-q">{m().common.search}</Field.Label><Input
				id="mp-q"
				name="q"
				type="search"
				value={data.filters.q}
			/>
		</Field.Field>
		{#if data.tab === 'products'}
			<Field.Field class="w-auto">
				<Field.Label for="mp-status">{m().common.status}</Field.Label>
				<NativeSelect.Root id="mp-status" name="status" value={data.filters.status}>
					<NativeSelect.Option value="">{m().common.all}</NativeSelect.Option>
					{#each ['DRAFT', 'ACTIVE', 'ARCHIVED', 'BLOCKED'] as s (s)}<NativeSelect.Option value={s}
							>{statusLabel(s)}</NativeSelect.Option
						>{/each}
				</NativeSelect.Root>
			</Field.Field>
		{/if}
	</FilterBar>
	{#if rows.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().merchant.productTitle}</Table.Head>
						<Table.Head>{m().catalog.soldBy}</Table.Head>
						<Table.Head class="text-end">{m().merchant.price}</Table.Head>
						<Table.Head>{m().common.status}</Table.Head>
						<Table.Head class="text-end"
							><span class="sr-only">{m().common.actions}</span></Table.Head
						>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each rows as r (r.id)}
						<Table.Row>
							<Table.Cell>
								<div class="flex items-center gap-3">
									<div class="size-10 shrink-0 overflow-hidden rounded-md bg-surface-2">
										<Picture src={r.image} alt="" fallback={r.title} />
									</div>
									<a
										href={r.href}
										target="_blank"
										class="max-w-64 truncate font-medium hover:underline"><bdi>{r.title}</bdi></a
									>
									{#if r.featured}<StarIcon
											class="size-4 shrink-0 fill-rating text-rating"
											aria-label={t.feature}
										/>{/if}
								</div>
							</Table.Cell>
							<Table.Cell class="text-ink-2">{r.store}</Table.Cell>
							<Table.Cell class="text-end tabular">{fmt.money(r.price)}</Table.Cell>
							<Table.Cell><StatusBadge status={r.status} /></Table.Cell>
							<Table.Cell class="text-end">
								<DropdownMenu.Root>
									<DropdownMenu.Trigger>
										{#snippet child({ props })}<Button
												{...props}
												size="icon-sm"
												variant="ghost"
												aria-label="{m().common.actions}: {r.title}"><EllipsisIcon /></Button
											>{/snippet}
									</DropdownMenu.Trigger>
									<DropdownMenu.Content align="end">
										{#if r.status === 'BLOCKED'}
											<DropdownMenu.Item onclick={() => moderate(r.id, 'unblock')}
												>{t.unblock}</DropdownMenu.Item
											>
										{:else}
											<DropdownMenu.Item
												variant="destructive"
												onclick={() => moderate(r.id, 'block')}>{t.block}</DropdownMenu.Item
											>
										{/if}
										<DropdownMenu.Item
											onclick={() => moderate(r.id, r.featured ? 'unfeature' : 'feature')}
											>{r.featured ? t.unfeature : t.feature}</DropdownMenu.Item
										>
									</DropdownMenu.Content>
								</DropdownMenu.Root>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator total={paged.total} page={paged.page} pageSize={paged.page_size} />
	{:else}
		<EmptyState icon={BadgeCheckIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>
