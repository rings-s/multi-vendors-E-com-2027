<script lang="ts">
	import MinusIcon from '@lucide/svelte/icons/minus';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as ButtonGroup from '#lib/components/ui/button-group/index.js';
	import { m, fmt } from '#lib/i18n/state.svelte.js';

	interface Props {
		value: number;
		min?: number;
		max?: number;
		disabled?: boolean;
		label?: string;
		onchange?: (value: number) => void;
	}

	let {
		value = $bindable(1),
		min = 1,
		max = 999,
		disabled = false,
		label,
		onchange
	}: Props = $props();

	function set(next: number) {
		const v = Math.min(max, Math.max(min, next));
		if (v === value) return;
		value = v;
		onchange?.(v);
	}
</script>

<ButtonGroup.Root aria-label={label ?? m().catalog.quantity}>
	<Button
		variant="outline"
		size="icon-lg"
		aria-label={m().ui.decrease}
		disabled={disabled || value <= min}
		onclick={() => set(value - 1)}
	>
		<MinusIcon />
	</Button>
	<ButtonGroup.Text
		class="min-w-10 justify-center bg-background tabular"
		aria-live="polite"
		data-testid="quantity"
	>
		{fmt.number(value)}
	</ButtonGroup.Text>
	<Button
		variant="outline"
		size="icon-lg"
		aria-label={m().ui.increase}
		disabled={disabled || value >= max}
		onclick={() => set(value + 1)}
	>
		<PlusIcon />
	</Button>
</ButtonGroup.Root>
