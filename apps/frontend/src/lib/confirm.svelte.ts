/**
 * Promise-based confirmation dialogs, rendered once by `<ConfirmHost />` in the root
 * layout (shadcn-svelte AlertDialog).
 *
 *   if (await confirm({ title: m().cart.clearConfirm, destructive: true })) …
 *   const reason = await prompt({ title: m().merchant.rejectReason, minLength: 3 });
 */
export interface ConfirmOptions {
	title: string;
	description?: string;
	confirmLabel?: string;
	cancelLabel?: string;
	destructive?: boolean;
}

export interface PromptOptions extends ConfirmOptions {
	label?: string;
	minLength?: number;
	optional?: boolean;
	initial?: string;
	multiline?: boolean;
}

interface Request extends PromptOptions {
	kind: 'confirm' | 'prompt';
	resolve: (value: string | boolean | null) => void;
}

class ConfirmController {
	current = $state<Request | null>(null);

	settle(value: string | boolean | null) {
		const req = this.current;
		this.current = null;
		req?.resolve(value);
	}
}

export const confirmController = new ConfirmController();

export function confirm(opts: ConfirmOptions): Promise<boolean> {
	return new Promise((resolve) => {
		confirmController.current?.resolve(false);
		confirmController.current = { ...opts, kind: 'confirm', resolve: (v) => resolve(v === true) };
	});
}

/** Ask for a short text (e.g. a reason). Resolves `null` when cancelled. */
export function prompt(opts: PromptOptions): Promise<string | null> {
	return new Promise((resolve) => {
		confirmController.current?.resolve(null);
		confirmController.current = {
			multiline: true,
			...opts,
			kind: 'prompt',
			resolve: (v) => resolve(typeof v === 'string' ? v : null)
		};
	});
}
