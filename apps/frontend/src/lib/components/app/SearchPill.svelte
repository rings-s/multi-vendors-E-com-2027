<script lang="ts">
	import { goto } from '$app/navigation';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import SearchIcon from '@lucide/svelte/icons/search';
	import * as InputGroup from '#lib/components/ui/input-group/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		value?: string;
		size?: 'md' | 'lg';
		placeholder?: string;
		class?: string;
		/** Called after a search is submitted (e.g. to close a menu). */
		onsearch?: (term: string) => void;
	}

	let {
		value = $bindable(''),
		size = 'md',
		placeholder,
		class: className,
		onsearch
	}: Props = $props();

	function submit(e: SubmitEvent) {
		e.preventDefault();
		const term = value.trim();
		onsearch?.(term);
		void goto(term ? `/search?q=${encodeURIComponent(term)}` : '/search');
	}
</script>

<!-- Pill search with the circular violet submit — the system's signature control. -->
<form role="search" action="/search" class={cn('w-full', className)} onsubmit={submit}>
	<InputGroup.Root
		class={cn(
			'shadow-pill transition-shadow focus-within:shadow-float',
			size === 'lg' ? 'h-14 ps-2' : 'h-11'
		)}
	>
		<InputGroup.Addon>
			<SearchIcon class={size === 'lg' ? 'size-5' : undefined} />
		</InputGroup.Addon>
		<InputGroup.Input
			type="search"
			name="q"
			bind:value
			placeholder={placeholder ?? m().common.searchPlaceholder}
			aria-label={m().common.search}
			class={size === 'lg' ? 'text-base tracking-[-0.031em]' : undefined}
		/>
		<InputGroup.Addon align="inline-end">
			<InputGroup.Button
				type="submit"
				variant="default"
				size="icon-sm"
				class={cn(
					'rounded-full shadow-brand hover:shadow-brand',
					size === 'lg' ? 'size-11' : 'size-8'
				)}
				aria-label={m().common.search}
			>
				<ArrowRightIcon class="rtl-flip" />
			</InputGroup.Button>
		</InputGroup.Addon>
	</InputGroup.Root>
</form>
