<script lang="ts">
	import { invalidate } from '$app/navigation';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { api, call } from '#lib/api/client.js';
	import type { Category } from '#lib/api/types.js';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { m, pick, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	type Kind = 'PRODUCT' | 'SERVICE' | 'BOTH';
	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	const form = new FormState();
	let open = $state(false);
	let editing = $state<Category | null>(null);
	let v = $state({
		slug: '',
		name_en: '',
		name_ar: '',
		kind: 'BOTH' as Kind,
		parent_id: '',
		is_active: true,
		sort_order: 0
	});

	function edit(c: Category | null) {
		editing = c;
		v = c
			? {
					slug: c.slug,
					name_en: c.name_en,
					name_ar: c.name_ar,
					kind: c.kind as Kind,
					parent_id: c.parent_id ?? '',
					is_active: c.is_active,
					sort_order: c.sort_order
				}
			: {
					slug: '',
					name_en: '',
					name_ar: '',
					kind: 'BOTH',
					parent_id: '',
					is_active: true,
					sort_order: data.categories.length
				};
		form.reset();
		open = true;
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		const body = { ...v, parent_id: v.parent_id || null, sort_order: Number(v.sort_order) || 0 };
		const res = await form.submit(
			() =>
				editing
					? call(
							api.PATCH('/api/v1/admin/categories/{category_id}', {
								params: { path: { category_id: editing.id } },
								body
							})
						)
					: call(api.POST('/api/v1/admin/categories', { body })),
			{ success: m().common.saved }
		);
		if (res.ok) {
			open = false;
			await invalidate('app:categories');
		}
	}
	const parentName = (id: string | null) => {
		const p = data.categories.find((c) => c.id === id);
		return p ? pick(p, 'name') : '—';
	};
</script>

<svelte:head><title>{t.categories} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.categories}>
		{#snippet actions()}<Button onclick={() => edit(null)}
				><PlusIcon data-icon="inline-start" />{t.newCategory}</Button
			>{/snippet}
	</PageHeader>
	<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>{t.nameEn}</Table.Head>
					<Table.Head>{t.nameAr}</Table.Head>
					<Table.Head>{t.slug}</Table.Head>
					<Table.Head>{t.kind}</Table.Head>
					<Table.Head>{t.parent}</Table.Head>
					<Table.Head class="text-end">{t.sortOrder}</Table.Head>
					<Table.Head>{m().common.status}</Table.Head>
					<Table.Head><span class="sr-only">{m().common.actions}</span></Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each data.categories as c (c.id)}
					<Table.Row>
						<Table.Cell class="font-medium" dir="ltr">{c.name_en}</Table.Cell>
						<Table.Cell dir="rtl" lang="ar">{c.name_ar}</Table.Cell>
						<Table.Cell class="text-ink-2" dir="ltr">{c.slug}</Table.Cell>
						<Table.Cell>{statusLabel(c.kind)}</Table.Cell>
						<Table.Cell class="text-ink-2">{parentName(c.parent_id)}</Table.Cell>
						<Table.Cell class="text-end tabular">{c.sort_order}</Table.Cell>
						<Table.Cell><StatusBadge status={c.is_active ? 'ACTIVE' : 'INACTIVE'} /></Table.Cell>
						<Table.Cell class="text-end"
							><Button
								size="icon-sm"
								variant="ghost"
								aria-label="{m().common.edit}: {c.name_en}"
								onclick={() => edit(c)}><PencilIcon /></Button
							></Table.Cell
						>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
</div>

<Dialog.Root bind:open>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={save} novalidate>
			<Dialog.Header
				><Dialog.Title>{editing ? m().common.edit : t.newCategory}</Dialog.Title></Dialog.Header
			>
			<Field.Group>
				{#if form.message}<Alert.Root variant="destructive"
						><Alert.Description>{form.message}</Alert.Description></Alert.Root
					>{/if}
				<div class="grid gap-4 sm:grid-cols-2">
					<FormField label={t.nameEn} id="c-en" error={form.errors.name_en}
						>{#snippet children({ id, invalid })}<Input
								{id}
								dir="ltr"
								bind:value={v.name_en}
								aria-invalid={invalid || undefined}
							/>{/snippet}</FormField
					>
					<FormField label={t.nameAr} id="c-ar" error={form.errors.name_ar}
						>{#snippet children({ id, invalid })}<Input
								{id}
								dir="rtl"
								lang="ar"
								bind:value={v.name_ar}
								aria-invalid={invalid || undefined}
							/>{/snippet}</FormField
					>
					<FormField label={t.slug} id="c-slug" error={form.errors.slug}
						>{#snippet children({ id, invalid })}<Input
								{id}
								dir="ltr"
								bind:value={v.slug}
								disabled={!!editing}
								aria-invalid={invalid || undefined}
							/>{/snippet}</FormField
					>
					<FormField label={t.kind} id="c-kind">
						{#snippet children({ id })}
							<NativeSelect.Root {id} bind:value={v.kind} class="w-full">
								{#each ['PRODUCT', 'SERVICE', 'BOTH'] as k (k)}<NativeSelect.Option value={k}
										>{statusLabel(k)}</NativeSelect.Option
									>{/each}
							</NativeSelect.Root>
						{/snippet}
					</FormField>
					<FormField label={t.parent} id="c-parent" optional>
						{#snippet children({ id })}
							<NativeSelect.Root {id} bind:value={v.parent_id} class="w-full">
								<NativeSelect.Option value="">{m().common.none}</NativeSelect.Option>
								{#each data.categories.filter((c) => c.id !== editing?.id && !c.parent_id) as c (c.id)}<NativeSelect.Option
										value={c.id}>{pick(c, 'name')}</NativeSelect.Option
									>{/each}
							</NativeSelect.Root>
						{/snippet}
					</FormField>
					<FormField label={t.sortOrder} id="c-sort"
						>{#snippet children({ id })}<Input
								{id}
								type="number"
								bind:value={v.sort_order}
							/>{/snippet}</FormField
					>
				</div>
				<Field.Field orientation="horizontal">
					<Switch id="c-active" bind:checked={v.is_active} /><Field.Label
						for="c-active"
						class="font-normal">{t.active}</Field.Label
					>
				</Field.Field>
			</Field.Group>
			<Dialog.Footer>
				<Button type="button" variant="ghost" onclick={() => (open = false)}
					>{m().common.cancel}</Button
				>
				<Button type="submit" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().common.save}</Button
				>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
