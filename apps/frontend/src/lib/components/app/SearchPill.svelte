<script lang="ts">
	import { goto } from '$app/navigation';
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

<!-- The marketplace search: one rounded field with the brand submit at its end. -->
<form role="search" action="/search" class={cn('w-full', className)} onsubmit={submit}>
	<InputGroup.Root
		class={cn(
			'rounded-full bg-surface-2 ps-2 transition-[background-color,border-color,box-shadow] duration-150 focus-within:bg-card hover:border-line-strong dark:bg-surface-2',
			size === 'lg' ? 'h-13' : 'h-11'
		)}
	>
		<InputGroup.Input
			type="search"
			name="q"
			bind:value
			placeholder={placeholder ?? m().common.searchPlaceholder}
			aria-label={m().common.search}
			class={cn('ps-3', size === 'lg' && 'text-base')}
		/>
		<InputGroup.Addon align="inline-end" class="pe-1">
			<InputGroup.Button
				type="submit"
				variant="default"
				size="icon-sm"
				class={cn('rounded-full', size === 'lg' ? 'size-10' : 'size-8.5')}
				aria-label={m().common.search}
			>
				<SearchIcon />
			</InputGroup.Button>
		</InputGroup.Addon>
	</InputGroup.Root>
</form>
