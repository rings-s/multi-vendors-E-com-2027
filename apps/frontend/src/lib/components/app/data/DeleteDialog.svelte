<script lang="ts">
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';
	import { toast } from 'svelte-sonner';
	import { api, call } from '#lib/api/client.js';
	import type { DataDeletePreview } from '#lib/api/types.js';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as AlertDialog from '#lib/components/ui/alert-dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { dataUrl, fieldLabel, modelLabel } from '#lib/data-admin.js';
	import { errorMessage, fmt, m } from '#lib/i18n/state.svelte.js';

	/**
	 * Delete confirmation (Django's "Are you sure?" page): lists what will be deleted,
	 * what cascades, what gets unlinked, and any protected references that block it.
	 */
	interface Props {
		open: boolean;
		model: string;
		pks: string[];
		ondeleted?: (count: number) => void;
	}

	let { open = $bindable(), model, pks, ondeleted }: Props = $props();

	const t = $derived(m().data);
	let preview = $state<DataDeletePreview | null>(null);
	let loadError = $state<string | null>(null);
	let pending = $state(false);
	let seq = 0;

	$effect(() => {
		if (!open || pks.length === 0) return;
		const mine = ++seq;
		preview = null;
		loadError = null;
		call(
			api.POST('/api/v1/admin/data/{model}/delete-preview', {
				params: { path: { model } },
				body: { pks }
			})
		)
			.then((p) => mine === seq && (preview = p))
			.catch((e) => mine === seq && (loadError = errorMessage(e)));
	});

	const blocked = $derived((preview?.protected.length ?? 0) > 0);

	async function confirmDelete() {
		pending = true;
		try {
			const res =
				pks.length === 1
					? await call(
							api.DELETE('/api/v1/admin/data/{model}/{pk}', {
								params: { path: { model, pk: pks[0] } }
							})
						)
					: await call(
							api.POST('/api/v1/admin/data/{model}/bulk-delete', {
								params: { path: { model } },
								body: { pks }
							})
						);
			toast.success(`${t.deleted}: ${fmt.number(res.deleted)}`);
			open = false;
			ondeleted?.(res.deleted);
		} catch (e) {
			toast.error(errorMessage(e));
		} finally {
			pending = false;
		}
	}
</script>

<AlertDialog.Root bind:open>
	<AlertDialog.Content class="sm:max-w-lg">
		<AlertDialog.Header>
			<AlertDialog.Title>{blocked ? t.deleteBlocked : t.confirmDelete}</AlertDialog.Title>
			<AlertDialog.Description>{modelLabel(t, model)}</AlertDialog.Description>
		</AlertDialog.Header>

		<div class="grid max-h-[60vh] gap-4 overflow-y-auto text-sm">
			{#if loadError}
				<Alert.Root variant="destructive"
					><Alert.Description>{loadError}</Alert.Description></Alert.Root
				>
			{:else if !preview}
				<div class="flex justify-center p-6"><Spinner /></div>
			{:else}
				{#if blocked}
					<Alert.Root variant="destructive">
						<TriangleAlertIcon />
						<Alert.Description>
							<p>{t.protectedIntro}</p>
							<ul class="mt-2 list-disc ps-5">
								{#each preview.protected as p (p.model + p.field)}
									<li>
										<a
											class="underline underline-offset-4"
											href="{dataUrl(p.model)}?{p.field}__in={encodeURIComponent(pks.join(','))}"
											>{modelLabel(t, p.model)}</a
										>
										({fieldLabel(t, p.field)}): {fmt.number(p.count)}
									</li>
								{/each}
							</ul>
						</Alert.Description>
					</Alert.Root>
				{/if}
				<section>
					<p class="font-medium">{t.deleteIntro}</p>
					<ul class="mt-2 list-disc ps-5 text-ink-2">
						{#each preview.objects as o (o.pk)}
							<li>{o.label}</li>
						{/each}
					</ul>
				</section>
				{#if preview.cascades.length}
					<section>
						<p class="font-medium">{t.cascadeIntro}</p>
						<ul class="mt-2 list-disc ps-5 text-ink-2">
							{#each preview.cascades as c (c.model)}
								<li>{modelLabel(t, c.model)}: {fmt.number(c.count)}</li>
							{/each}
						</ul>
					</section>
				{/if}
				{#if preview.unlinks.length}
					<section>
						<p class="font-medium">{t.unlinkIntro}</p>
						<ul class="mt-2 list-disc ps-5 text-ink-2">
							{#each preview.unlinks as u (u.model + u.field)}
								<li>{modelLabel(t, u.model)} ({fieldLabel(t, u.field)}): {fmt.number(u.count)}</li>
							{/each}
						</ul>
					</section>
				{/if}
			{/if}
		</div>

		<AlertDialog.Footer>
			<AlertDialog.Cancel>{m().common.cancel}</AlertDialog.Cancel>
			{#if !blocked}
				<Button variant="destructive" disabled={!preview || pending} onclick={confirmDelete}
					>{#if pending}<Spinner data-icon="inline-start" />{/if}{m().common.delete}</Button
				>
			{/if}
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>
