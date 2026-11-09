/**
 * Minimal form state for API-backed forms: pending flag, translated field errors
 * (from the backend's `validation_failed` details) and a form-level message.
 *
 *   const form = new FormState();
 *   await form.submit(() => call(api.POST(...)), { success: m().common.saved });
 *   <FormField error={form.errors.email}> … </FormField>
 */
import { toast } from 'svelte-sonner';
import { isApiError } from '#lib/api/errors.js';
import { errorMessage } from '#lib/i18n/state.svelte.js';

export class FormState {
	pending = $state(false);
	errors = $state<Record<string, string>>({});
	message = $state<string | null>(null);

	reset() {
		this.errors = {};
		this.message = null;
	}

	/** Set a client-side validation error (already translated). */
	fail(field: string, message: string) {
		this.errors = { ...this.errors, [field]: message };
	}

	get hasErrors() {
		return Object.keys(this.errors).length > 0;
	}

	async submit<T>(
		fn: () => Promise<T>,
		opts: { success?: string; toastError?: boolean } = {}
	): Promise<{ ok: true; data: T } | { ok: false }> {
		if (this.pending) return { ok: false };
		this.pending = true;
		this.message = null;
		this.errors = {};
		try {
			const data = await fn();
			if (opts.success) toast.success(opts.success);
			return { ok: true, data };
		} catch (e) {
			this.message = errorMessage(e);
			if (isApiError(e)) this.errors = e.fieldErrors;
			if (opts.toastError !== false) toast.error(this.message);
			return { ok: false };
		} finally {
			this.pending = false;
		}
	}
}

/** Run a one-off API action with toast feedback; returns the data or `undefined`. */
export async function action<T>(fn: () => Promise<T>, success?: string): Promise<T | undefined> {
	try {
		const data = await fn();
		if (success) toast.success(success);
		return data;
	} catch (e) {
		toast.error(errorMessage(e));
		return undefined;
	}
}
