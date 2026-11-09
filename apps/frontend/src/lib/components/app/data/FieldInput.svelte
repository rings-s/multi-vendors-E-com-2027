<script lang="ts">
	import type { DataField } from '#lib/api/types.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import type { FormValue } from '#lib/data-admin.js';
	import { m, statusLabel } from '#lib/i18n/state.svelte.js';
	import RecordPicker from './RecordPicker.svelte';

	/** The form control for one column, chosen by its kind (Django's form widgets). */
	interface Props {
		field: DataField;
		id: string;
		value: FormValue;
		fkLabel?: string | null;
		invalid?: boolean;
		describedBy?: string;
		creating?: boolean;
	}

	let {
		field,
		id,
		value = $bindable(),
		fkLabel = null,
		invalid = false,
		describedBy,
		creating = false
	}: Props = $props();

	const t = $derived(m().data);
	const aria = $derived({
		'aria-invalid': invalid || undefined,
		'aria-describedby': describedBy
	});
	const numeric = $derived(['integer', 'money', 'float', 'decimal'].includes(field.kind));
	const longText = $derived(
		field.kind === 'text' || (field.kind === 'string' && (field.max_length ?? 0) > 500)
	);
	// Text controls bind through a string view of the value (booleans only use the switch).
	const getText = () => (typeof value === 'string' ? value : String(value));
	const setText = (v: string) => (value = v);
</script>

{#if field.fk}
	<RecordPicker
		{id}
		model={field.fk}
		bind:value={getText, setText}
		label={fkLabel}
		nullable={field.nullable}
		{invalid}
		{describedBy}
	/>
{:else if field.kind === 'boolean' && !field.nullable}
	<Switch
		{id}
		checked={value === true}
		onCheckedChange={(v) => (value = v)}
		aria-describedby={describedBy}
	/>
{:else if field.kind === 'boolean'}
	<NativeSelect.Root {id} bind:value={getText, setText} class="w-full sm:w-48" {...aria}>
		<NativeSelect.Option value="">{t.nullValue}</NativeSelect.Option>
		<NativeSelect.Option value="true">{m().common.yes}</NativeSelect.Option>
		<NativeSelect.Option value="false">{m().common.no}</NativeSelect.Option>
	</NativeSelect.Root>
{:else if field.choices}
	<NativeSelect.Root {id} bind:value={getText, setText} class="w-full" {...aria}>
		{#if field.nullable || creating}
			<NativeSelect.Option value="">{field.nullable ? t.nullValue : '—'}</NativeSelect.Option>
		{/if}
		{#each field.choices as choice (choice)}
			<NativeSelect.Option value={choice}>{statusLabel(choice)} ({choice})</NativeSelect.Option>
		{/each}
	</NativeSelect.Root>
{:else if field.kind === 'json'}
	<Textarea
		{id}
		bind:value={getText, setText}
		rows={6}
		dir="ltr"
		spellcheck={false}
		class="font-mono text-xs"
		placeholder={'{}'}
		{...aria}
	/>
{:else if field.kind === 'datetime'}
	<Input
		{id}
		type="datetime-local"
		step="1"
		dir="ltr"
		bind:value={getText, setText}
		class="sm:w-64"
		{...aria}
	/>
{:else if field.kind === 'password'}
	<Input
		{id}
		type="password"
		autocomplete="new-password"
		bind:value={getText, setText}
		maxlength={128}
		{...aria}
	/>
{:else if longText}
	<Textarea
		{id}
		bind:value={getText, setText}
		rows={4}
		maxlength={field.max_length ?? undefined}
		{...aria}
	/>
{:else}
	<Input
		{id}
		bind:value={getText, setText}
		inputmode={numeric
			? field.kind === 'integer' || field.kind === 'money'
				? 'numeric'
				: 'decimal'
			: undefined}
		dir={numeric || field.kind === 'uuid' ? 'ltr' : 'auto'}
		maxlength={field.max_length ?? undefined}
		class={numeric ? 'tabular sm:w-64' : undefined}
		{...aria}
	/>
{/if}
