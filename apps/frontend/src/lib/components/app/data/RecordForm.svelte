<script lang="ts">
	import { goto, invalidate } from '$app/navigation';
	import { api, call } from '#lib/api/client.js';
	import type { DataModelSchema, DataRowDetail } from '#lib/api/types.js';
	import FormField from '#lib/components/app/FormField.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import {
		JsonFieldError,
		dataUrl,
		fieldLabel,
		formFields,
		isEditable,
		toFormValues,
		toPayload
	} from '#lib/data-admin.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import CellValue from './CellValue.svelte';
	import FieldInput from './FieldInput.svelte';

	/** Add / change form for any table, generated from its schema (Django's ModelForm). */
	interface Props {
		schema: DataModelSchema;
		/** The record being changed; `null` to add one. */
		row: DataRowDetail | null;
		/** Initial values for a new record (e.g. from `?field=value` in the URL). */
		initial?: Record<string, string>;
		ondelete?: () => void;
	}

	let { schema, row, initial = {}, ondelete }: Props = $props();

	const t = $derived(m().data);
	const creating = $derived(row === null);
	const canWrite = $derived(
		schema.user_can_manage && (creating ? schema.can_add : schema.can_change)
	);
	const form = new FormState();

	// The form is rebuilt from props whenever the record (or schema) changes.
	const start = $derived.by(() => {
		const values = toFormValues(schema, row?.values ?? null);
		if (!row) for (const [k, v] of Object.entries(initial)) if (k in values) values[k] = v;
		return values;
	});
	let values = $derived({ ...start });
	const fkLabels = $derived(row?.fk_labels ?? {});
	const fields = $derived(formFields(schema, creating));

	type Next = 'list' | 'add' | 'continue';

	async function save(next: Next) {
		form.reset();
		let body: Record<string, unknown>;
		try {
			body = toPayload(schema, values, start, creating);
		} catch (e) {
			if (e instanceof JsonFieldError) form.fail(e.field, t.jsonInvalid);
			return;
		}
		const res = await form.submit(
			() =>
				row
					? call(
							api.PATCH('/api/v1/admin/data/{model}/{pk}', {
								params: { path: { model: schema.key, pk: row.pk } },
								body
							})
						)
					: call(
							api.POST('/api/v1/admin/data/{model}', {
								params: { path: { model: schema.key } },
								body
							})
						),
			{ success: creating ? t.created : t.updated }
		);
		if (!res.ok) return;
		if (next === 'list') await goto(dataUrl(schema.key));
		else if (next === 'add') {
			if (creating) values = toFormValues(schema, null);
			else await goto(`${dataUrl(schema.key)}/new`);
		} else if (creating) await goto(dataUrl(schema.key, res.data.pk));
		else await invalidate('app:data-record');
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		const submitter = e.submitter as HTMLButtonElement | null;
		void save((submitter?.value as Next) || 'list');
	}

	function hint(kind: string): string | undefined {
		if (kind === 'money') return t.moneyHint;
		if (kind === 'json') return t.jsonHint;
		if (kind === 'decimal') return t.decimalHint;
		if (kind === 'datetime') return 'UTC';
		if (kind === 'password') return creating ? t.passwordNewHint : t.passwordHint;
		if (kind === 'uuid') return t.uuidHint;
		return undefined;
	}
</script>

<form class="grid gap-6" onsubmit={submit} novalidate>
	{#if form.message}
		<Alert.Root variant="destructive"
			><Alert.Description>{form.message}</Alert.Description></Alert.Root
		>
	{/if}

	<div class="divide-y divide-line rounded-2xl border border-line bg-surface">
		{#each fields as f (f.name)}
			{@const editable = canWrite && isEditable(schema, f, creating)}
			<div class="grid gap-2 p-4">
				{#if editable}
					<FormField
						label={fieldLabel(t, f.name)}
						id="f-{f.name}"
						error={form.errors[f.name]}
						hint={hint(f.kind)}
						optional={!f.required && f.kind !== 'boolean' && !(f.kind === 'password' && creating)}
					>
						{#snippet children({ id, invalid, describedBy })}
							<FieldInput
								field={f}
								{id}
								bind:value={values[f.name]}
								fkLabel={fkLabels[f.name]?.[String(values[f.name])] ?? null}
								{invalid}
								{describedBy}
								{creating}
							/>
						{/snippet}
					</FormField>
				{:else if f.kind !== 'password'}
					<div class="flex flex-wrap items-baseline gap-x-2 text-sm font-medium">
						{fieldLabel(t, f.name)}
						<span class="text-xs font-normal text-ink-3"
							>{f.primary_key ? t.primaryKey : t.readonly}</span
						>
					</div>
					<div class="min-w-0 text-sm break-words">
						<CellValue
							field={f}
							value={row?.values[f.name]}
							fkLabel={fkLabels[f.name]?.[String(row?.values[f.name])] ?? null}
						/>
					</div>
				{/if}
			</div>
		{/each}
	</div>

	<div class="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
		<div>
			{#if row && ondelete && schema.can_delete && schema.user_can_manage}
				<Button type="button" variant="destructive" onclick={ondelete}>{m().common.delete}</Button>
			{/if}
		</div>
		{#if canWrite}
			<div class="flex flex-col gap-2 sm:flex-row">
				{#if schema.can_add}
					<Button type="submit" variant="outline" value="add" disabled={form.pending}
						>{t.saveAndAdd}</Button
					>
				{/if}
				<Button type="submit" variant="outline" value="continue" disabled={form.pending}
					>{t.saveAndContinue}</Button
				>
				<Button type="submit" value="list" disabled={form.pending}
					>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().common.save}</Button
				>
			</div>
		{/if}
	</div>
</form>
