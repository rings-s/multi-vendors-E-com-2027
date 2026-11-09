/**
 * Helpers for the generic data admin (`/admin/data/*`, backed by `/api/v1/admin/data/*`).
 *
 * The backend describes every table (`ModelSchema`); these helpers turn that description
 * into labels, display values, form values and request payloads.
 */
import type { DataField, DataModelSchema } from '#lib/api/types.js';
import type { Messages } from '#lib/i18n/messages/en.js';

export type FormValue = string | boolean;
export type FormValues = Record<string, FormValue>;

const ACRONYMS: Record<string, string> = {
	id: 'ID',
	url: 'URL',
	ip: 'IP',
	vat: 'VAT',
	sku: 'SKU',
	iban: 'IBAN',
	eta: 'ETA',
	json: 'JSON'
};

/** `customer_user_id` → `Customer user`, `ip_address` → `IP address`. */
export function humanize(name: string): string {
	const words = name.replace(/_id$/, '').split('_').filter(Boolean);
	return words
		.map((w, i) => ACRONYMS[w] ?? (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
		.join(' ');
}

export function modelLabel(t: Messages['data'], key: string): string {
	return t.models[key] ?? humanize(key);
}

export function groupLabel(t: Messages['data'], key: string): string {
	return t.groups[key] ?? humanize(key);
}

export function fieldLabel(t: Messages['data'], name: string): string {
	return t.fields[name] ?? humanize(name);
}

export function noteText(t: Messages['data'], note: string): string {
	if (note === 'append_only') return t.noteAppendOnly;
	if (note === 'financial') return t.noteFinancial;
	if (note === 'system_generated') return t.noteSystemGenerated;
	return note;
}

export function dataUrl(model: string, pk?: string | null): string {
	return pk == null
		? `/admin/data/${encodeURIComponent(model)}`
		: `/admin/data/${encodeURIComponent(model)}/${encodeURIComponent(pk)}`;
}

/** ISO timestamp → `YYYY-MM-DDTHH:mm:ss` in UTC (for `<input type="datetime-local">`). */
export function isoToInput(iso: string | null | undefined): string {
	if (!iso) return '';
	const d = new Date(iso);
	return Number.isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 19);
}

/** `<input type="datetime-local">` value (UTC) → ISO timestamp. */
export function inputToIso(value: string): string {
	return value.length === 16 ? `${value}:00Z` : `${value}Z`;
}

const SYSTEM_FIELDS = new Set(['created_at', 'updated_at']);

/** Fields shown in the add / change form, in schema order (system fields last). */
export function formFields(schema: DataModelSchema, creating: boolean): DataField[] {
	// New records hide generated values (auto ids, timestamps); existing ones show them
	// read-only. As in Django, the key comes first and system timestamps last.
	const shown = creating ? schema.fields.filter((f) => !f.readonly) : schema.fields;
	const rank = (f: DataField) => (f.primary_key ? 0 : SYSTEM_FIELDS.has(f.name) ? 2 : 1);
	return shown.toSorted((a, b) => rank(a) - rank(b));
}

/** Whether a field can be edited in this form. */
export function isEditable(schema: DataModelSchema, f: DataField, creating: boolean): boolean {
	if (f.readonly) return false;
	if (f.primary_key) return creating && !schema.auto_pk;
	return true;
}

/** Initial form values from a record (or defaults for a new one). */
export function toFormValues(
	schema: DataModelSchema,
	values: Record<string, unknown> | null
): FormValues {
	const out: FormValues = {};
	for (const f of schema.fields) {
		const v = values?.[f.name];
		if (f.kind === 'password') out[f.name] = '';
		else if (f.kind === 'boolean') {
			if (v == null) out[f.name] = f.nullable ? '' : values ? false : defaultBoolean(f);
			else out[f.name] = f.nullable ? String(v) : Boolean(v);
		} else if (f.kind === 'datetime') out[f.name] = isoToInput(v as string | null);
		else if (f.kind === 'json') out[f.name] = v == null ? '' : JSON.stringify(v, null, 2);
		else out[f.name] = v == null ? '' : String(v);
	}
	return out;
}

/** New records: switches start "on" only for the conventional `is_active`-style flags. */
function defaultBoolean(f: DataField): boolean {
	return /^(is_active|is_available|is_open|delivery_enabled|refundable|requires_shipping)$/.test(
		f.name
	);
}

export class JsonFieldError extends Error {
	constructor(readonly field: string) {
		super(`Invalid JSON in ${field}`);
	}
}

function fieldPayload(f: DataField, v: FormValue): unknown {
	if (f.kind === 'boolean') {
		if (typeof v === 'boolean') return v;
		return v === '' ? null : v === 'true';
	}
	const text = String(v);
	if (f.kind === 'json') {
		if (!text.trim()) return null;
		try {
			return JSON.parse(text);
		} catch {
			throw new JsonFieldError(f.name);
		}
	}
	if (f.kind === 'datetime') return text ? inputToIso(text) : null;
	if (f.kind === 'string' || f.kind === 'text') return text === '' && f.nullable ? null : text;
	return text.trim() === '' ? null : text.trim();
}

/**
 * Request body: every editable field when creating (blank optional fields are left out so
 * model defaults apply), only the changed ones when editing.
 */
export function toPayload(
	schema: DataModelSchema,
	values: FormValues,
	initial: FormValues,
	creating: boolean
): Record<string, unknown> {
	const body: Record<string, unknown> = {};
	for (const f of schema.fields) {
		if (!isEditable(schema, f, creating)) continue;
		const v = values[f.name];
		if (v === undefined) continue;
		if (f.kind === 'password') {
			if (v) body[f.name] = v;
			continue;
		}
		if (creating) {
			if (v === '' && !f.required && f.kind !== 'boolean') continue;
		} else if (v === initial[f.name]) continue;
		body[f.name] = fieldPayload(f, v);
	}
	return body;
}

/** Lookup suffixes understood by the list endpoint (`?total__gte=…`). */
export const RESERVED_PARAMS = new Set(['page', 'page_size', 'q', 'ordering']);

/** Active filters from the URL (everything that is not paging / search / ordering). */
export function activeFilters(params: Pick<URLSearchParams, 'entries'>): [string, string][] {
	return [...params.entries()].filter(([k]) => !RESERVED_PARAMS.has(k));
}

// -- inlines (child rows edited on the parent's page, like Django's TabularInline) --------

export interface InlineRow {
	/** Primary key of an existing child row; `null` for a new one. */
	pk: string | null;
	values: FormValues;
	initial: FormValues;
	deleted: boolean;
}

export interface InlineState {
	model: string;
	fk: string;
	schema: DataModelSchema;
	rows: InlineRow[];
	fkLabels: Record<string, Record<string, string>>;
}

export function newInlineRow(schema: DataModelSchema): InlineRow {
	const values = toFormValues(schema, null);
	return { pk: null, values, initial: { ...values }, deleted: false };
}

export function existingInlineRow(
	schema: DataModelSchema,
	pk: string,
	values: Record<string, unknown>
): InlineRow {
	const form = toFormValues(schema, values);
	return { pk, values: form, initial: { ...form }, deleted: false };
}

/** Whether a new inline row has anything filled in (blank extra rows are ignored, as in Django). */
function touched(row: InlineRow): boolean {
	return Object.entries(row.values).some(([k, v]) => v !== row.initial[k]);
}

/**
 * `_inlines` items for one child table and, for each item, the index of the row it came
 * from (so `_inlines.<model>.<i>.<field>` errors can be shown on the right row).
 */
export function inlinePayload(state: InlineState): {
	items: Record<string, unknown>[];
	rows: number[];
} {
	const items: Record<string, unknown>[] = [];
	const rows: number[] = [];
	state.rows.forEach((row, index) => {
		if (row.pk === null) {
			if (row.deleted || !touched(row)) return;
			const body = toPayload(state.schema, row.values, row.initial, true);
			delete body[state.fk];
			items.push(body);
		} else if (row.deleted) {
			items.push({ _pk: row.pk, _delete: true });
		} else {
			const body = toPayload(state.schema, row.values, row.initial, false);
			delete body[state.fk];
			if (Object.keys(body).length === 0) return;
			items.push({ _pk: row.pk, ...body });
		}
		rows.push(index);
	});
	return { items, rows };
}

/** Changing or deleting existing rows of an append-only child is an override. */
export function inlineNeedsOverride(state: InlineState, items: Record<string, unknown>[]): boolean {
	return state.schema.immutable && items.some((item) => '_pk' in item);
}
