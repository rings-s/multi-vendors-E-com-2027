<script lang="ts">
	import ImagePlusIcon from '@lucide/svelte/icons/image-plus';
	import XIcon from '@lucide/svelte/icons/x';
	import { toast } from 'svelte-sonner';
	import { uploadImage, type UploadPurpose } from '#lib/api/client.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { errorMessage, m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	interface Img {
		url: string;
		alt?: string;
	}

	interface Props {
		/** Uploaded images, in display order. */
		images: Img[];
		purpose: UploadPurpose;
		max?: number;
		label: string;
		id: string;
		aspect?: string;
		class?: string;
	}

	let {
		images = $bindable([]),
		purpose,
		max = 8,
		label,
		id,
		aspect = 'aspect-square',
		class: className
	}: Props = $props();
	let uploading = $state(false);

	async function onFiles(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const files = [...(input.files ?? [])].slice(0, Math.max(0, max - images.length));
		input.value = '';
		if (!files.length) return;
		uploading = true;
		try {
			for (const file of files) {
				const url = await uploadImage(file, purpose);
				images = [...images, { url, alt: '' }];
			}
		} catch (err) {
			toast.error(errorMessage(err));
		} finally {
			uploading = false;
		}
	}

	function remove(i: number) {
		images = images.filter((_, j) => j !== i);
	}
</script>

<Field.Set class={className}>
	<Field.Legend variant="label" id="{id}-label">{label}</Field.Legend>
	<ul class="grid grid-cols-3 gap-3 sm:grid-cols-4" aria-labelledby="{id}-label">
		{#each images as img, i (img.url)}
			<li
				class={cn(
					'group relative overflow-hidden rounded-lg border border-line bg-surface-2',
					aspect
				)}
			>
				<img src={img.url} alt={img.alt ?? ''} class="size-full object-cover" />
				<Button
					type="button"
					variant="secondary"
					size="icon-sm"
					class="absolute end-1.5 top-1.5 rounded-full shadow-soft"
					aria-label={m().merchant.removeImage}
					onclick={() => remove(i)}
				>
					<XIcon />
				</Button>
				{#if i === 0 && max > 1}
					<Badge variant="secondary" class="absolute start-1.5 bottom-1.5">
						{m().merchant.primary}
					</Badge>
				{/if}
			</li>
		{/each}
		{#if images.length < max}
			<li class={aspect}>
				<!-- File drop target: the visually hidden file input is labelled by this tile. -->
				<label
					for={id}
					class="flex size-full cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-line-strong text-xs text-ink-3 transition-colors hover:bg-surface-2 has-focus-visible:ring-3 has-focus-visible:ring-ring/50"
				>
					{#if uploading}
						<Spinner />{m().merchant.uploading}
					{:else}
						<ImagePlusIcon class="size-5" aria-hidden="true" />{max > 1
							? m().merchant.addImage
							: m().merchant.upload}
					{/if}
					<input
						{id}
						type="file"
						accept="image/png,image/jpeg,image/webp"
						multiple={max > 1}
						class="sr-only"
						disabled={uploading}
						onchange={onFiles}
					/>
				</label>
			</li>
		{/if}
	</ul>
</Field.Set>
