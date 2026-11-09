<script lang="ts">
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import {
		dataUrl,
		fieldLabel,
		formFields,
		modelLabel,
		newInlineRow,
		type InlineState
	} from '#lib/data-admin.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import CellValue from './CellValue.svelte';
	import FieldInput from './FieldInput.svelte';

	/**
	 * Child rows edited on the parent's form (Django's TabularInline): existing rows can be
	 * changed or marked for deletion, and new rows added. Everything is saved with the parent.
	 */
	interface Props {
		state: InlineState;
		/** May add rows / change existing rows (append-only children need the override). */
		canAdd: boolean;
		canEdit: boolean;
		error: (row: number, field: string) => string | undefined;
	}

	let { state = $bindable(), canAdd, canEdit, error }: Props = $props();

	const t = $derived(m().data);
	const columns = $derived(formFields(state.schema, true).filter((f) => f.name !== state.fk));
	const headingId = $derived(`inline-${state.model}`);
</script>

<section class="rounded-2xl border border-line bg-surface" aria-labelledby={headingId}>
	<div class="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
		<h2 id={headingId} class="type-label">
			<a href={dataUrl(state.model)} class="hover:text-primary">{modelLabel(t, state.model)}</a>
		</h2>
		{#if canAdd}
			<Button
				type="button"
				size="sm"
				variant="ghost"
				onclick={() => (state.rows = [...state.rows, newInlineRow(state.schema)])}
				><PlusIcon data-icon="inline-start" />{t.inlineAdd}</Button
			>
		{/if}
	</div>
	<div class="overflow-x-auto">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					{#each columns as f (f.name)}
						<Table.Head>
							{fieldLabel(t, f.name)}{#if f.required}<span
									class="text-destructive"
									aria-hidden="true">*</span
								>{/if}
						</Table.Head>
					{/each}
					<Table.Head class="w-20 text-center">{t.inlineDelete}</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each state.rows as row, r (row.pk ?? `new-${r}`)}
					{@const editable = row.pk === null ? canAdd : canEdit}
					<Table.Row class={row.deleted ? 'opacity-50' : undefined}>
						{#each columns as f (f.name)}
							{@const err = error(r, f.name)}
							<Table.Cell class="min-w-40 align-top">
								{#if editable && !row.deleted}
									<FieldInput
										field={f}
										id="inline-{state.model}-{r}-{f.name}"
										bind:value={row.values[f.name]}
										fkLabel={state.fkLabels[f.name]?.[String(row.values[f.name])] ?? null}
										invalid={!!err}
										describedBy={err ? `inline-${state.model}-${r}-${f.name}-error` : undefined}
										creating={row.pk === null}
									/>
									{#if err}
										<p
											id="inline-{state.model}-{r}-{f.name}-error"
											class="mt-1 text-xs text-destructive"
										>
											{err}
										</p>
									{/if}
								{:else}
									<CellValue
										field={f}
										value={row.values[f.name]}
										fkLabel={state.fkLabels[f.name]?.[String(row.values[f.name])] ?? null}
										compact
									/>
								{/if}
							</Table.Cell>
						{/each}
						<Table.Cell class="text-center align-top">
							{#if row.pk === null}
								<Button
									type="button"
									size="sm"
									variant="ghost"
									onclick={() => (state.rows = state.rows.filter((_, i) => i !== r))}
									>{m().common.remove}</Button
								>
							{:else if canEdit}
								<Checkbox
									class="mt-2"
									bind:checked={row.deleted}
									aria-label="{t.inlineDelete}: {modelLabel(t, state.model)} {r + 1}"
								/>
							{/if}
						</Table.Cell>
					</Table.Row>
				{:else}
					<Table.Row>
						<Table.Cell colspan={columns.length + 1} class="text-sm text-ink-3"
							>{t.noRecords}</Table.Cell
						>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
</section>
