<script lang="ts" module>
	import type { Delivery } from '#lib/api/types.js';
	import type { Messages } from '#lib/i18n/messages/en.js';

	type StatusKey = keyof Messages['delivery']['statusLabel'];

	/** Customer-facing label of a delivery status (pickup "delivered" reads "collected"). */
	export function deliveryStatusLabel(m: Messages, d: Pick<Delivery, 'method' | 'status'>): string {
		if (d.method === 'PICKUP' && d.status === 'DELIVERED') return m.delivery.collected;
		if (d.method === 'PICKUP' && d.status === 'FAILED') return m.delivery.notCollected;
		return m.delivery.statusLabel[d.status as StatusKey] ?? d.status;
	}
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import PackageIcon from '@lucide/svelte/icons/package';
	import StoreIcon from '@lucide/svelte/icons/store';
	import TruckIcon from '@lucide/svelte/icons/truck';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { etaRange, formatAddress, mapsLink } from '#lib/delivery.js';
	import { fmt, locale, m } from '#lib/i18n/state.svelte.js';
	import StatusBadge from './StatusBadge.svelte';

	interface Props {
		delivery: Delivery;
		/** Show who receives the fee and who bears the cost (merchant and admin views). */
		showTerms?: boolean;
		actions?: Snippet;
	}

	let { delivery: d, showTerms = false, actions }: Props = $props();
	const pickup = $derived(d.method === 'PICKUP');
	const place = $derived(
		(pickup ? d.pickup_location : d.address) as Record<string, unknown> | null
	);
	const pin = $derived.by(() => {
		if (!pickup && d.latitude != null && d.longitude != null)
			return [d.latitude, d.longitude] as const;
		const lat = place?.latitude;
		const lng = place?.longitude;
		return pickup && typeof lat === 'number' && typeof lng === 'number'
			? ([lat, lng] as const)
			: null;
	});
	const window = $derived(etaRange(d.eta_min_minutes, d.eta_max_minutes, locale()));
	const finished = $derived(d.status === 'DELIVERED' || d.status === 'CANCELLED');
	const events = $derived(d.events ?? []);
	const statusKey = (s: string) => m().delivery.statusLabel[s as StatusKey] ?? s;
</script>

<Card.Root data-testid="delivery-card">
	<Card.Header>
		<Card.Title role="heading" aria-level={2} class="flex items-center gap-2">
			{#if pickup}<StoreIcon class="size-4" aria-hidden="true" />{:else}<TruckIcon
					class="size-4"
					aria-hidden="true"
				/>{/if}
			{pickup ? m().delivery.pickupFromStore : m().delivery.deliverToAddress}
		</Card.Title>
		<Card.Action>
			<StatusBadge status={d.status} label={deliveryStatusLabel(m(), d)} />
		</Card.Action>
		{#if !finished}
			<Card.Description>
				{#if d.estimated_latest_at}
					{m().delivery.expectedBy({ date: fmt.datetime(d.estimated_latest_at) })}
				{:else}
					{pickup ? m().delivery.readyIn({ range: window }) : m().delivery.eta({ range: window })}
				{/if}
			</Card.Description>
		{/if}
	</Card.Header>
	<Card.Content class="flex flex-col gap-5 text-sm">
		{#if d.status === 'FAILED' && d.failure_reason}
			<Alert.Root variant="warning">
				<Alert.Title>{deliveryStatusLabel(m(), d)}</Alert.Title>
				<Alert.Description>{d.failure_reason}</Alert.Description>
			</Alert.Root>
		{/if}

		{#if place}
			<div class="flex flex-col gap-1">
				<p class="text-ink-3">{pickup ? m().delivery.pickupPoint : m().orders.deliveryTo}</p>
				{#if pickup && place.label}<p class="font-medium"><bdi>{place.label}</bdi></p>{/if}
				{#if !pickup && place.recipient_name}
					<p class="font-medium">
						<bdi>{place.recipient_name}</bdi>{#if place.phone}
							· <span dir="ltr" class="tabular">{fmt.phone(String(place.phone))}</span>{/if}
					</p>
				{/if}
				<p class="text-ink-2">{formatAddress(place, fmt.region, fmt.list)}</p>
				{#if !pickup && place.additional_info}<p class="text-ink-3">{place.additional_info}</p>{/if}
				{#if pin}
					<a
						href={mapsLink(pin[0], pin[1])}
						target="_blank"
						rel="noopener noreferrer"
						class="inline-flex items-center gap-1 self-start text-brand underline underline-offset-2"
						><MapPinIcon class="size-3.5" aria-hidden="true" />{m().delivery.openInMaps}</a
					>
				{/if}
			</div>
		{/if}

		{#if d.instructions}
			<div class="flex flex-col gap-1">
				<p class="text-ink-3">{m().delivery.instructions}</p>
				<p class="whitespace-pre-line"><bdi>{d.instructions}</bdi></p>
			</div>
		{/if}

		<dl class="grid grid-cols-2 gap-x-4 gap-y-2">
			{#if d.zone_name}
				<dt class="text-ink-3">{m().delivery.zone}</dt>
				<dd>{d.zone_name}</dd>
			{/if}
			{#if !pickup}
				<dt class="text-ink-3">{m().delivery.fee}</dt>
				<dd class="tabular">
					{d.fee === 0 ? m().delivery.free : fmt.money(d.fee)}
					{#if d.fee_waived}<span class="block text-xs text-success"
							>{m().delivery.waived({ amount: fmt.money(d.fee_waived) })}</span
						>{/if}
				</dd>
			{/if}
			{#if d.attempts > 1}
				<dt class="text-ink-3"><PackageIcon class="inline size-3.5" aria-hidden="true" /></dt>
				<dd>{m().delivery.attempts({ n: d.attempts })}</dd>
			{/if}
			{#if showTerms && d.fee_recipient && !pickup}
				<dt class="text-ink-3">{m().delivery.feeRecipient}</dt>
				<dd>{m().delivery.party[d.fee_recipient as 'MERCHANT'] ?? d.fee_recipient}</dd>
			{/if}
			{#if showTerms && d.cost_bearer}
				<dt class="text-ink-3">{m().delivery.costBearer}</dt>
				<dd>{m().delivery.party[d.cost_bearer as 'MERCHANT'] ?? d.cost_bearer}</dd>
			{/if}
		</dl>

		{#if events.length}
			<div class="flex flex-col gap-2">
				<p class="text-ink-3">{m().delivery.timeline}</p>
				<ol class="flex flex-col gap-2 border-s border-line ps-4">
					{#each events as e, i (i)}
						<li class="relative">
							<span
								class="absolute -start-[1.3rem] top-1.5 size-2 rounded-full bg-ink-3"
								aria-hidden="true"
							></span>
							<p class="font-medium">
								{pickup && e.to_status === 'DELIVERED'
									? m().delivery.collected
									: statusKey(e.to_status)}
							</p>
							<p class="text-xs text-ink-3">
								{fmt.datetime(e.created_at)} · {m().delivery.source[e.source as 'SYSTEM'] ??
									e.source}
							</p>
							{#if e.note}<p class="text-ink-2"><bdi>{e.note}</bdi></p>{/if}
						</li>
					{/each}
				</ol>
			</div>
		{/if}
	</Card.Content>
	{#if actions}
		<Card.Footer class="flex flex-wrap gap-2">{@render actions()}</Card.Footer>
	{/if}
</Card.Root>
