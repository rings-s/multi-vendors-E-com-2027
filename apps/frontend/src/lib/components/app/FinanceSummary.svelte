<script lang="ts">
	import type { FinancialSummary } from '#lib/api/types.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import StatCard from './StatCard.svelte';

	/** All figures come from the backend ledger; nothing is derived on the client. */
	let { summary }: { summary: FinancialSummary } = $props();
</script>

<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" data-testid="finance-summary">
	<StatCard
		label={m().merchant.netEarnings}
		value={fmt.money(summary.net_earnings)}
		tone="brand"
		hint={m().merchant.paidOrders + ': ' + fmt.number(summary.paid_orders)}
	/>
	<StatCard
		label={m().merchant.totalSales}
		value={fmt.money(summary.gross_sales)}
		hint={m().delivery.productSales + ': ' + fmt.money(summary.product_sales)}
	/>
	<StatCard
		label={m().delivery.deliveryCharges}
		value={fmt.money(summary.delivery_charges)}
		hint={m().delivery.deliveryEarnings + ': ' + fmt.money(summary.delivery_earnings)}
	/>
	<StatCard label={m().delivery.itemCommission} value={fmt.money(summary.platform_commission)} />
	<StatCard
		label={m().delivery.platformDeliveryShare}
		value={fmt.money(summary.platform_delivery_share)}
		hint={summary.delivery_commission_note || undefined}
	/>
	<StatCard
		label={m().merchant.processingFees}
		value={fmt.money(summary.processing_fees_borne)}
		hint={summary.fee_bearer_note || undefined}
	/>
	<StatCard label={m().merchant.pendingSettlement} value={fmt.money(summary.pending_settlement)} />
	<StatCard
		label={m().merchant.completedSettlements}
		value={fmt.money(summary.completed_settlements)}
	/>
	<StatCard
		label={m().merchant.refundsTotal}
		value={fmt.money(summary.refunds)}
		hint={summary.delivery_refunds
			? m().delivery.deliveryRefunds + ': ' + fmt.money(summary.delivery_refunds)
			: undefined}
	/>
	<StatCard
		label={m().merchant.chargebacksTotal}
		value={fmt.money(summary.chargebacks)}
		tone={summary.chargebacks > 0 ? 'danger' : 'default'}
	/>
</div>
