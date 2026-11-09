<script lang="ts">
	import { goto, invalidate } from '$app/navigation';
	import { page } from '$app/state';
	import ArrowDownIcon from '@lucide/svelte/icons/arrow-down';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import ArrowUpIcon from '@lucide/svelte/icons/arrow-up';
	import ArrowUpDownIcon from '@lucide/svelte/icons/arrow-up-down';
	import InfoIcon from '@lucide/svelte/icons/info';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import SearchIcon from '@lucide/svelte/icons/search';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import XIcon from '@lucide/svelte/icons/x';
	import type { DataField } from '#lib/api/types.js';
	import CellValue from '#lib/components/app/data/CellValue.svelte';
	import DeleteDialog from '#lib/components/app/data/DeleteDialog.svelte';
	import RecordPicker from '#lib/components/app/data/RecordPicker.svelte';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import * as InputGroup from '#lib/components/ui/input-group/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import {
		activeFilters,
		dataUrl,
		fieldLabel,
		groupLabel,
		modelLabel,
		noteText
	} from '#lib/data-admin.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().data);
	const schema = $derived(data.schema);
	const rows = $derived(data.rows);
	const fields = $derived(new Map(schema.fields.map((f) => [f.name, f])));
	const columns = $derived(
		schema.list_display.map((n) => fields.get(n)).filter((f): f is DataField => !!f)
	);
	const title = $derived(modelLabel(t, schema.key));
	const canDelete = $derived(schema.can_delete && schema.user_can_manage);

	let q = $derived(page.url.searchParams.get('q') ?? '');
	let selected = $state<string[]>([]);
	let deleteOpen = $state(false);
	let deleting = $state<string[]>([]);

	// Selection is per page: reset it whenever the listed rows change.
	$effect(() => {
		void rows;
		selected = [];
	});

	const pagePks = $derived(rows.items.map((r) => r.pk));
	const allSelected = $derived(pagePks.length > 0 && pagePks.every((p) => selected.includes(p)));
	const someSelected = $derived(selected.length > 0 && !allSelected);

	function navigate(update: (params: URLSearchParams) => void) {
		const url = new URL(page.url.href);
		update(url.searchParams);
		url.searchParams.delete('page');
		void goto(url, { reset: false });
	}

	function setParam(name: string, value: string) {
		navigate((p) => (value ? p.set(name, value) : p.delete(name)));
	}

	function search(e: SubmitEvent) {
		e.preventDefault();
		setParam('q', q.trim());
	}

	// Ordering: click cycles ascending → descending → default.
	const ordering = $derived(page.url.searchParams.get('ordering') ?? '');
	function sortState(name: string): 'asc' | 'desc' | null {
		if (ordering === name) return 'asc';
		if (ordering === `-${name}`) return 'desc';
		return null;
	}
	function toggleSort(name: string) {
		const s = sortState(name);
		setParam('ordering', s === null ? name : s === 'asc' ? `-${name}` : '');
	}

	// Sidebar-style filters (Django's list_filter).
	const filterFields = $derived(
		schema.list_filter.map((n) => fields.get(n)).filter((f): f is DataField => !!f)
	);
	function filterParam(f: DataField): string {
		return f.kind === 'datetime' || (!f.choices && f.kind !== 'boolean' && !f.fk)
			? `${f.name}__isnull`
			: f.name;
	}
	const filters = $derived(activeFilters(page.url.searchParams));
	const filterLabel = (key: string) => {
		const [name, lookup] = key.split('__');
		return lookup ? `${fieldLabel(t, name)} (${lookup})` : fieldLabel(t, name);
	};
	const filterValueLabel = (key: string, value: string) => {
		const name = key.split('__')[0];
		const f = fields.get(name);
		if (key.endsWith('__isnull')) return value === 'true' ? t.isNull : t.notNull;
		if (f?.kind === 'boolean') return value === 'true' ? m().common.yes : m().common.no;
		if (f?.choices) return statusLabel(value);
		if (f?.fk) return rows.fk_labels[name]?.[value] ?? value.slice(0, 8);
		return value;
	};

	function toggleRow(pk: string, on: boolean) {
		selected = on ? [...selected, pk] : selected.filter((p) => p !== pk);
	}

	function askDelete(pks: string[]) {
		deleting = pks;
		deleteOpen = true;
	}
</script>

<svelte:head><title>{title} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader {title} eyebrow={groupLabel(t, schema.group)}>
		{#snippet meta()}
			<p class="text-sm text-ink-3">
				<code dir="ltr">{schema.key}</code> · {m().common.results({ count: rows.total })}
			</p>
		{/snippet}
		{#snippet actions()}
			<Button variant="ghost" href="/admin/data"
				><ArrowLeftIcon data-icon="inline-start" class="rtl:rotate-180" />{t.nav}</Button
			>
			{#if schema.can_add && schema.user_can_manage}
				<Button href="{dataUrl(schema.key)}/new{page.url.search}"
					><PlusIcon data-icon="inline-start" />{t.addRecord}</Button
				>
			{/if}
		{/snippet}
	</PageHeader>

	{#each schema.notes as note (note)}
		<Alert.Root variant={note === 'financial' ? 'warning' : 'default'}>
			<InfoIcon />
			<Alert.Description>{noteText(t, note)}</Alert.Description>
		</Alert.Root>
	{/each}
	{#if !schema.user_can_manage}
		<Alert.Root>
			<InfoIcon />
			<Alert.Description>{t.noPermission}</Alert.Description>
		</Alert.Root>
	{/if}

	<div class="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-3 sm:p-4">
		<form class="flex flex-col gap-2 sm:flex-row" onsubmit={search} role="search">
			<InputGroup.Root class="w-full">
				<InputGroup.Addon><SearchIcon /></InputGroup.Addon>
				<InputGroup.Input
					type="search"
					bind:value={q}
					aria-label={t.searchRecords}
					placeholder={schema.search_fields.length
						? `${t.searchIn}: ${schema.search_fields.map((n) => fieldLabel(t, n)).join(', ')}`
						: t.searchRecords}
				/>
			</InputGroup.Root>
			<Button type="submit" variant="outline">{m().common.search}</Button>
		</form>

		{#if filterFields.length}
			<div class="flex flex-wrap items-end gap-3">
				{#each filterFields as f (f.name)}
					{@const param = filterParam(f)}
					{@const current = page.url.searchParams.get(param) ?? ''}
					<label class="grid gap-1 text-xs font-medium text-ink-2">
						{t.filterBy}: {fieldLabel(t, f.name)}
						{#if f.fk}
							<div class="w-60">
								<RecordPicker
									id="filter-{f.name}"
									model={f.fk}
									value={current}
									label={rows.fk_labels[f.name]?.[current] ?? null}
									nullable
									onchange={(v) => setParam(param, v)}
								/>
							</div>
						{:else}
							<NativeSelect.Root
								size="sm"
								value={current}
								onchange={(e) => setParam(param, e.currentTarget.value)}
							>
								<NativeSelect.Option value="">{t.any}</NativeSelect.Option>
								{#if param.endsWith('__isnull')}
									<NativeSelect.Option value="false">{t.notNull}</NativeSelect.Option>
									<NativeSelect.Option value="true">{t.isNull}</NativeSelect.Option>
								{:else if f.kind === 'boolean'}
									<NativeSelect.Option value="true">{m().common.yes}</NativeSelect.Option>
									<NativeSelect.Option value="false">{m().common.no}</NativeSelect.Option>
								{:else}
									{#each f.choices ?? [] as c (c)}
										<NativeSelect.Option value={c}>{statusLabel(c)}</NativeSelect.Option>
									{/each}
								{/if}
							</NativeSelect.Root>
						{/if}
					</label>
				{/each}
			</div>
		{/if}

		{#if filters.length || page.url.searchParams.get('q')}
			<div class="flex flex-wrap items-center gap-2">
				{#each filters as [key, value] (key + value)}
					<Badge variant="secondary" class="h-7 gap-1 pe-1">
						{filterLabel(key)}: {filterValueLabel(key, value)}
						<button
							type="button"
							class="rounded-full p-0.5 hover:bg-background"
							aria-label="{t.clear}: {filterLabel(key)}"
							onclick={() => setParam(key, '')}><XIcon class="size-3" /></button
						>
					</Badge>
				{/each}
				<Button size="sm" variant="link" href={dataUrl(schema.key)}>{t.clearFilters}</Button>
			</div>
		{/if}
	</div>

	{#if canDelete && selected.length}
		<div
			class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface-2 px-4 py-2"
			role="region"
			aria-label={m().common.actions}
		>
			<p class="text-sm tabular">{fmt.number(selected.length)} {t.selected}</p>
			<Button size="sm" variant="destructive" onclick={() => askDelete(selected)}
				><Trash2Icon data-icon="inline-start" />{t.deleteSelected}</Button
			>
		</div>
	{/if}

	{#if rows.items.length === 0}
		<EmptyState title={t.noRecords} />
	{:else}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						{#if canDelete}
							<Table.Head class="w-10">
								<Checkbox
									checked={allSelected}
									indeterminate={someSelected}
									aria-label={t.selectAll}
									onCheckedChange={(on) => (selected = on ? [...pagePks] : [])}
								/>
							</Table.Head>
						{/if}
						{#each columns as f (f.name)}
							{@const s = sortState(f.name)}
							<Table.Head
								aria-sort={s === 'asc' ? 'ascending' : s === 'desc' ? 'descending' : undefined}
								class={f.kind === 'money' || f.kind === 'integer' ? 'text-end' : undefined}
							>
								{#if f.kind === 'json'}
									{fieldLabel(t, f.name)}
								{:else}
									<button
										type="button"
										class="inline-flex items-center gap-1 hover:text-ink"
										onclick={() => toggleSort(f.name)}
										aria-label="{fieldLabel(t, f.name)}: {s === 'asc' ? t.sortDesc : t.sortAsc}"
									>
										{fieldLabel(t, f.name)}
										{#if s === 'asc'}<ArrowUpIcon
												class="size-3.5"
											/>{:else if s === 'desc'}<ArrowDownIcon
												class="size-3.5"
											/>{:else}<ArrowUpDownIcon class="size-3.5 opacity-40" />{/if}
									</button>
								{/if}
							</Table.Head>
						{/each}
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each rows.items as row (row.pk)}
						<Table.Row data-state={selected.includes(row.pk) ? 'selected' : undefined}>
							{#if canDelete}
								<Table.Cell>
									<Checkbox
										checked={selected.includes(row.pk)}
										aria-label="{t.selectRow}: {row.label}"
										onCheckedChange={(on) => toggleRow(row.pk, on)}
									/>
								</Table.Cell>
							{/if}
							{#each columns as f, i (f.name)}
								<Table.Cell
									class={f.kind === 'money' || f.kind === 'integer' ? 'text-end' : undefined}
								>
									{#if i === 0}
										<a
											href={dataUrl(schema.key, row.pk)}
											class="font-medium text-primary underline-offset-4 hover:underline"
										>
											{#if row.values[f.name] == null || row.values[f.name] === ''}
												<bdi>{row.label}</bdi>
											{:else if f.fk}
												{rows.fk_labels[f.name]?.[String(row.values[f.name])] ?? row.label}
											{:else if f.kind === 'datetime'}
												{fmt.datetime(String(row.values[f.name]))}
											{:else if f.kind === 'money'}
												{fmt.money(Number(row.values[f.name]))}
											{:else}
												<span class="block max-w-72 truncate">{String(row.values[f.name])}</span>
											{/if}
										</a>
									{:else}
										<CellValue
											field={f}
											value={row.values[f.name]}
											fkLabel={rows.fk_labels[f.name]?.[String(row.values[f.name])] ?? null}
											compact
										/>
									{/if}
								</Table.Cell>
							{/each}
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}

	<Paginator total={rows.total} page={rows.page} pageSize={rows.page_size} />
</div>

<DeleteDialog
	bind:open={deleteOpen}
	model={schema.key}
	pks={deleting}
	ondeleted={() => invalidate('app:data-list')}
/>
