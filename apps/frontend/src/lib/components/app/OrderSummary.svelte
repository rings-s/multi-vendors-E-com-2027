<script lang="ts">
	import type { Snippet } from 'svelte';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';

	/** Totals exactly as calculated by the backend; nothing is recomputed here. */
	interface Props {
		subtotal: number;
		discount: number;
		/** Delivery fee excl. VAT (0 for pickup). */
		delivery: number;
		/** NONE hides the line; PICKUP shows a free pickup line. */
		deliveryMethod?: string;
		/** The fee is not known yet (no address chosen). */
		deliveryPending?: boolean;
		vat: number;
		total: number;
		vatRate?: string | null;
		children?: Snippet;
	}

	let {
		subtotal,
		discount,
		delivery,
		deliveryMethod = 'DELIVERY',
		deliveryPending = false,
		vat,
		total,
		vatRate,
		children
	}: Props = $props();
</script>

<dl class="flex flex-col gap-2.5 text-sm tabular">
	<div class="flex justify-between gap-4">
		<dt class="text-ink-2">{m().cart.subtotal}</dt>
		<dd>{fmt.money(subtotal)}</dd>
	</div>
	{#if discount > 0}
		<div class="flex justify-between gap-4 text-success">
			<dt>{m().cart.discount}</dt>
			<dd>−{fmt.money(discount)}</dd>
		</div>
	{/if}
	{#if deliveryMethod !== 'NONE'}
		<div class="flex justify-between gap-4">
			<dt class="text-ink-2">
				{deliveryMethod === 'PICKUP' ? m().delivery.pickupFee : m().delivery.fee}
			</dt>
			<dd data-testid="delivery-fee">
				{#if deliveryPending}<span class="text-ink-3">{m().delivery.pending}</span
					>{:else}{delivery === 0 ? m().cart.free : fmt.money(delivery)}{/if}
			</dd>
		</div>
	{/if}
	<div class="flex justify-between gap-4">
		<dt class="text-ink-2">
			{vatRate && Number(vatRate) > 0
				? m().cart.vat({ rate: String(Number(vatRate)) })
				: m().cart.vatPlain}
		</dt>
		<dd>{fmt.money(vat)}</dd>
	</div>
	<Separator class="my-0.5" />
	<div class="flex justify-between gap-4 text-base font-medium">
		<dt>{m().cart.total}</dt>
		<dd data-testid="order-total">{fmt.money(total)}</dd>
	</div>
	{@render children?.()}
</dl>
