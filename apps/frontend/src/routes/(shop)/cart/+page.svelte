<script lang="ts">
	import { isolate } from '#lib/i18n/bidi.js';
	import { page } from '$app/state';
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import InfoIcon from '@lucide/svelte/icons/info';
	import ShoppingBagIcon from '@lucide/svelte/icons/shopping-bag';
	import StoreIcon from '@lucide/svelte/icons/store';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import TruckIcon from '@lucide/svelte/icons/truck';
	import { api, call } from '#lib/api/client.js';
	import type { Quote } from '#lib/api/types.js';
	import { cart } from '#lib/cart.svelte.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import OrderSummary from '#lib/components/app/OrderSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Picture from '#lib/components/app/Picture.svelte';
	import QuantityStepper from '#lib/components/app/QuantityStepper.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { confirm } from '#lib/confirm.svelte.js';
	import { etaRange } from '#lib/delivery.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, locale, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	let quote = $state<Quote | null>(null);
	let busy = $state(false);
	$effect(() => {
		quote = data.quote;
		cart.set(data.quote);
	});
	const user = $derived(page.data.user);

	const issueText = (code: string) =>
		(m().issues as Record<string, string>)[code] ?? m().errors.generic;

	async function mutate(fn: () => Promise<Quote>) {
		busy = true;
		const next = await action(fn);
		if (next) {
			quote = next;
			cart.set(next);
		}
		busy = false;
	}

	const setQty = (id: string, quantity: number) =>
		mutate(() =>
			call(
				api.PATCH('/api/v1/cart/items/{item_id}', {
					params: { path: { item_id: id } },
					body: { quantity }
				})
			)
		);
	const remove = (id: string) =>
		mutate(() =>
			call(api.DELETE('/api/v1/cart/items/{item_id}', { params: { path: { item_id: id } } }))
		);

	async function clear() {
		if (
			await confirm({
				title: m().cart.clearConfirm,
				destructive: true,
				confirmLabel: m().cart.clear
			})
		) {
			await mutate(() => call(api.DELETE('/api/v1/cart')));
		}
	}
</script>

<svelte:head><title>{m().cart.title} · {m().brand.name}</title></svelte:head>

<div class="container-page py-12">
	{#if !user}
		<EmptyState icon={ShoppingBagIcon} title={m().cart.title} description={m().catalog.signInToBuy}>
			<Button href="/sign-in?next=/cart">{m().nav.signIn}</Button>
		</EmptyState>
	{:else if !quote}
		<EmptyState
			icon={ShoppingBagIcon}
			title={m().cart.title}
			description={m().catalog.customerOnly}
		/>
	{:else if quote.groups.length === 0}
		<EmptyState icon={ShoppingBagIcon} title={m().cart.empty} description={m().cart.emptyBody}>
			<Button href="/stores">{m().cart.continueShopping}</Button>
		</EmptyState>
	{:else}
		<PageHeader title={m().cart.title} description={m().cart.items({ n: quote.item_count })}>
			{#snippet actions()}
				<Button variant="ghost" onclick={clear} disabled={busy}
					><Trash2Icon data-icon="inline-start" />{m().cart.clear}</Button
				>
			{/snippet}
		</PageHeader>

		<div class="mt-8 grid gap-10 lg:grid-cols-[1fr_22rem]">
			<div class="flex flex-col gap-6">
				{#if quote.groups.length > 1}
					<Alert.Root>
						<InfoIcon />
						<Alert.Description>{m().cart.separatePayments}</Alert.Description>
					</Alert.Root>
				{/if}
				{#each quote.groups as group (group.merchant_id)}
					<Card.Root
						role="region"
						aria-labelledby="g-{group.store_id}"
						data-testid="cart-group"
						class="gap-0 pb-0 sm:pb-0"
					>
						<Card.Header class="border-b">
							<Card.Title role="heading" aria-level={2} id="g-{group.store_id}">
								<a href="/stores/{group.store_slug}" class="hover:underline"
									>{m().cart.fromStore({ store: isolate(group.store_name) })}</a
								>
							</Card.Title>
							<Card.Action class="text-sm text-ink-3 tabular"
								>{m().cart.perStoreTotal}: {fmt.money(group.total)}</Card.Action
							>
						</Card.Header>
						{#if group.issues.length}
							<Alert.Root
								variant="destructive"
								class="rounded-none border-x-0 border-t-0 px-5 py-3"
							>
								<CircleAlertIcon />
								<Alert.Description>{group.issues.map(issueText).join(' · ')}</Alert.Description>
							</Alert.Root>
						{/if}
						<Item.Group class="gap-0">
							{#each group.lines as line, li (line.cart_item_id)}
								{#if li > 0}<Item.Separator class="my-0" />{/if}
								<Item.Root
									role="listitem"
									class="flex-nowrap items-start gap-4 rounded-none p-5"
									data-testid="cart-line"
								>
									<a
										href={line.product_id
											? `/products/${line.product_id}`
											: `/services/${line.service_id}`}
										class="size-20 shrink-0 overflow-hidden rounded-lg bg-surface-2 sm:size-24"
									>
										<Picture src={line.image_url} alt={line.title} fallback={line.title} />
									</a>
									<div class="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:justify-between">
										<Item.Content class="min-w-0">
											<Item.Title class="line-clamp-2"><bdi>{line.title}</bdi></Item.Title>
											{#if line.sku}<p class="text-xs text-ink-3" dir="ltr">{line.sku}</p>{/if}
											<p class="text-sm text-ink-2 tabular">
												{fmt.money(line.unit_price - line.unit_discount)}
												{#if line.unit_discount > 0}<s class="ms-1 text-ink-3"
														>{fmt.money(line.unit_price)}</s
													>{/if}
											</p>
											{#each line.issues as issue (issue)}
												<Alert.Root variant="destructive"
													><Alert.Description>{issueText(issue)}</Alert.Description></Alert.Root
												>
											{/each}
										</Item.Content>
										<div class="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
											<p class="font-medium tabular">{fmt.money(line.line_total)}</p>
											<div class="flex items-center gap-2">
												{#if line.item_type !== 'SERVICE'}
													<QuantityStepper
														value={line.quantity}
														max={Math.max(line.quantity, line.available_quantity ?? 999)}
														disabled={busy}
														onchange={(q) => line.cart_item_id && setQty(line.cart_item_id, q)}
													/>
												{/if}
												<Button
													variant="ghost"
													size="icon"
													aria-label="{m().cart.remove}: {line.title}"
													disabled={busy}
													onclick={() => line.cart_item_id && remove(line.cart_item_id)}
												>
													<Trash2Icon />
												</Button>
											</div>
										</div>
									</div>
								</Item.Root>
							{/each}
						</Item.Group>
						{#if group.requires_delivery && group.delivery}
							{@const d = group.delivery}
							<div
								class="flex flex-wrap items-center gap-x-3 gap-y-1 border-t px-5 py-3 text-sm text-ink-2"
								data-testid="cart-delivery"
							>
								{#if d.method === 'PICKUP'}<StoreIcon
										class="size-4"
										aria-hidden="true"
									/>{:else}<TruckIcon class="size-4" aria-hidden="true" />{/if}
								<span class="font-medium text-ink">{m().delivery.method[d.method]}</span>
								{#if group.delivery_pending}
									<span>{m().delivery.pendingHint}</span>
								{:else if d.available}
									<span class="tabular"
										>{group.delivery_fee === 0
											? m().delivery.free
											: fmt.money(group.delivery_fee)}</span
									>
									<span class="text-ink-3"
										>{d.method === 'PICKUP'
											? m().delivery.readyIn({
													range: etaRange(d.eta_min_minutes, d.eta_max_minutes, locale())
												})
											: m().delivery.eta({
													range: etaRange(d.eta_min_minutes, d.eta_max_minutes, locale())
												})}</span
									>
									{#if d.free_delivery_threshold && group.delivery_fee > 0}
										<span class="text-success"
											>{m().delivery.freeOver({
												amount: fmt.money(d.free_delivery_threshold)
											})}</span
										>
									{/if}
								{/if}
							</div>
						{/if}
					</Card.Root>
				{/each}
			</div>

			<aside class="h-fit lg:sticky lg:top-24">
				<Card.Root class="h-full">
					<Card.Header>
						<Card.Title role="heading" aria-level={2}>{m().checkout.summary}</Card.Title>
					</Card.Header>
					<Card.Content class="flex flex-col gap-5">
						<OrderSummary
							subtotal={quote.items_subtotal}
							discount={quote.discount_total}
							delivery={quote.delivery_total}
							deliveryMethod={quote.requires_delivery ? 'DELIVERY' : 'NONE'}
							deliveryPending={quote.groups.some((g) => g.delivery_pending)}
							vat={quote.vat_total}
							total={quote.total}
						/>
						{#if !quote.can_checkout}
							<Alert.Root variant="destructive"
								><Alert.Description>{m().cart.cannotCheckout}</Alert.Description></Alert.Root
							>
						{/if}
					</Card.Content>
					<Card.Footer class="flex-col items-stretch gap-3">
						<Button
							href={quote.can_checkout ? '/checkout' : undefined}
							size="lg"
							class="w-full"
							disabled={!quote.can_checkout || busy}
							data-testid="go-checkout"
						>
							{m().cart.checkout}
						</Button>
						<p class="text-xs text-ink-3">{m().checkout.priceNote}</p>
					</Card.Footer>
				</Card.Root>
			</aside>
		</div>
	{/if}
</div>
