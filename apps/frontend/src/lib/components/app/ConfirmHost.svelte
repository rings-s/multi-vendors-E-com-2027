<script lang="ts">
	import * as AlertDialog from '#lib/components/ui/alert-dialog/index.js';
	import { buttonVariants } from '#lib/components/ui/button/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { confirmController } from '#lib/confirm.svelte.js';
	import { m } from '#lib/i18n/state.svelte.js';

	const req = $derived(confirmController.current);
	let text = $state('');
	let touched = $state(false);

	$effect(() => {
		if (req) {
			text = req.initial ?? '';
			touched = false;
		}
	});

	const tooShort = $derived(
		req?.kind === 'prompt' && !req.optional && text.trim().length < (req.minLength ?? 1)
	);

	function onOpenChange(open: boolean) {
		if (!open && confirmController.current)
			confirmController.settle(req?.kind === 'prompt' ? null : false);
	}

	function accept(e: Event) {
		if (!req) return;
		if (req.kind === 'prompt') {
			touched = true;
			if (tooShort) {
				e.preventDefault();
				return;
			}
			confirmController.settle(text.trim());
		} else {
			confirmController.settle(true);
		}
	}
</script>

<AlertDialog.Root open={!!req} {onOpenChange}>
	<AlertDialog.Content>
		{#if req}
			<AlertDialog.Header>
				<AlertDialog.Title>{req.title}</AlertDialog.Title>
				{#if req.description}
					<AlertDialog.Description>{req.description}</AlertDialog.Description>
				{/if}
			</AlertDialog.Header>
			{#if req.kind === 'prompt'}
				<Field.Field data-invalid={touched && tooShort ? true : undefined}>
					<Field.Label for="confirm-input">{req.label ?? m().common.reason}</Field.Label>
					{#if req.multiline}
						<Textarea
							id="confirm-input"
							bind:value={text}
							rows={3}
							aria-invalid={touched && tooShort ? true : undefined}
						/>
					{:else}
						<Input
							id="confirm-input"
							bind:value={text}
							aria-invalid={touched && tooShort ? true : undefined}
						/>
					{/if}
					{#if touched && tooShort}
						<Field.Error>{m().errors.codes.reason_required}</Field.Error>
					{/if}
				</Field.Field>
			{/if}
			<AlertDialog.Footer>
				<AlertDialog.Cancel>{req.cancelLabel ?? m().common.cancel}</AlertDialog.Cancel>
				<AlertDialog.Action
					class={req.destructive ? buttonVariants({ variant: 'destructive' }) : undefined}
					onclick={accept}
				>
					{req.confirmLabel ?? m().common.confirm}
				</AlertDialog.Action>
			</AlertDialog.Footer>
		{/if}
	</AlertDialog.Content>
</AlertDialog.Root>
