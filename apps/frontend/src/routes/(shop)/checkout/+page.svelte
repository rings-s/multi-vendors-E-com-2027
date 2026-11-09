<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import InfoIcon from '@lucide/svelte/icons/info';
	import LockIcon from '@lucide/svelte/icons/lock';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { api, call, idempotencyKey } from '#lib/api/client.js';
	import { untrack } from 'svelte';
	import type {
		Address,
		CheckoutRequest,
		DeliverySelection,
		Quote,
		QuoteGroup
	} from '#lib/api/types.js';
	import AddressFields, {
		addressBody,
		type AddressValue
	} from '#lib/components/app/AddressFields.svelte';
	import FormField from '#lib/components/app/FormField.svelte';
	import OrderSummary from '#lib/components/app/OrderSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import TestModeBadge from '#lib/components/app/TestModeBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { etaRange } from '#lib/delivery.js';
	import * as RadioGroup from '#lib/components/ui/radio-group/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { cart } from '#lib/cart.svelte.js';
	import { normalizeSaudiMobile } from '#lib/format.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { fmt, locale, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	// Re-priced by the backend whenever the address or a delivery choice changes.
	let live = $state<Quote | null>(null);
	const quote = $derived(live ?? data.quote);
	const mock = $derived(!!page.data.payments?.mock_payments);

	// One key per checkout attempt: retrying the same submission can never create two orders.
	const key = idempotencyKey();
	const form = new FormState();
	const addrForm = new FormState();

	let addresses = $state<Address[]>([]);
	let addressId = $state('');
	let contactName = $state('');
	let contactPhone = $state('');
	let contactEmail = $state('');
	let method = $state<NonNullable<CheckoutRequest['payment_method']>>('card');
	let terms = $state(false);
	let addingAddress = $state(false);
	let instructions = $state('');
	type Choice = { method: 'DELIVERY' | 'PICKUP'; pickup_location_id: string | null };
	let choices = $state<Record<string, Choice>>({});
	let quoting = $state(false);
	let quoteSeq = 0;

	// Options the store actually offers (not-offered methods are hidden, not shown as errors).
	const offered = (g: QuoteGroup) =>
		g.delivery_options.filter(
			(o) => o.issue !== 'delivery_not_offered' && o.issue !== 'pickup_not_offered'
		);
	const deliveries = (): DeliverySelection[] =>
		Object.entries(choices).map(([store_id, c]) => ({
			store_id,
			method: c.method,
			pickup_location_id: c.method === 'PICKUP' ? c.pickup_location_id : null
		}));

	async function requote() {
		const seq = ++quoteSeq;
		quoting = true;
		try {
			const next = await call(
				api.POST('/api/v1/checkout/quote', {
					body: { address_id: addressId || null, deliveries: deliveries() }
				})
			);
			if (seq === quoteSeq) live = next;
		} catch {
			// Keep the previous quote; checkout re-validates everything on the server.
		} finally {
			if (seq === quoteSeq) quoting = false;
		}
	}

	function choose(storeId: string, method: Choice['method'], pickupId: string | null = null) {
		choices[storeId] = { method, pickup_location_id: pickupId };
		void requote();
	}

	$effect(() => {
		void addressId; // re-price when the delivery address changes
		untrack(() => void requote());
	});
	let newAddress = $state<AddressValue & { recipient_name: string; phone: string; label: string }>({
		label: '',
		recipient_name: '',
		phone: '',
		region: '',
		city: ''
	});

	$effect.pre(() => {
		addresses = data.addresses;
		addressId = (data.addresses.find((a) => a.is_default) ?? data.addresses[0])?.id ?? '';
		contactName = data.me.full_name;
		contactPhone = data.me.phone ?? '';
		contactEmail = data.me.email;
		method = mock ? 'mock' : 'card';
		addingAddress = data.quote.needs_address && data.addresses.length === 0;
		instructions =
			(data.addresses.find((a) => a.is_default) ?? data.addresses[0])?.delivery_instructions ?? '';
		choices = Object.fromEntries(
			data.quote.groups
				.filter((g) => g.requires_delivery && g.delivery_method !== 'NONE')
				.map((g) => [
					g.store_id,
					{
						method: g.delivery_method as Choice['method'],
						pickup_location_id: g.delivery?.pickup_location?.id ?? null
					}
				])
		);
	});

	const methods = $derived(
		mock
			? [{ value: 'mock', label: m().checkout.methodMock }]
			: [
					{ value: 'card', label: m().checkout.methodCard },
					{ value: 'applepay', label: m().checkout.methodApplePay },
					{ value: 'stcpay', label: m().checkout.methodStcPay }
				]
	);

	async function saveAddress() {
		const phone = normalizeSaudiMobile(newAddress.phone);
		if (!phone) return addrForm.fail('phone', m().errors.invalidPhone);
		const res = await addrForm.submit(() =>
			call(
				api.POST('/api/v1/customers/addresses', {
					body: addressBody({ ...newAddress, phone, is_default: addresses.length === 0 })
				})
			)
		);
		if (res.ok) {
			addresses = [...addresses, res.data];
			addressId = res.data.id;
			addingAddress = false;
		}
	}

	async function placeOrder(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const phone = normalizeSaudiMobile(contactPhone);
		if (!phone) form.fail('contact_phone', m().errors.invalidPhone);
		if (quote.needs_address && !addressId)
			form.fail('address_id', m().errors.codes.address_required);
		if (!terms) form.fail('accept_terms', m().errors.codes.terms_not_accepted);
		if (form.hasErrors) return;
		const res = await form.submit(() =>
			call(
				api.POST('/api/v1/checkout', {
					params: { header: { 'Idempotency-Key': key } },
					body: {
						address_id: quote.needs_address ? addressId : null,
						deliveries: deliveries(),
						delivery_instructions: quote.needs_address ? instructions.trim() || null : null,
						contact_name: contactName,
						contact_phone: phone!,
						contact_email: contactEmail || null,
						accept_terms: terms,
						payment_method: method
					}
				})
			)
		);
		if (res.ok) {
			cart.clear();
			await goto(`/checkout/pay/${res.data.id}`, { replaceState: true });
		}
	}
</script>

<svelte:head><title>{m().checkout.title} · {m().brand.name}</title></svelte:head>

<div class="container-page py-12">
	<PageHeader title={m().checkout.title}>
		{#snippet actions()}{#if mock}<TestModeBadge />{/if}{/snippet}
	</PageHeader>

	<form class="mt-8 grid gap-10 lg:grid-cols-[1fr_24rem]" onsubmit={placeOrder} novalidate>
		<div class="flex flex-col gap-8">
			<Card.Root>
				<Card.Header>
					<Card.Title role="heading" aria-level={2} id="contact-h"
						>{m().checkout.contact}</Card.Title
					>
				</Card.Header>
				<Card.Content>
					<Field.Group class="grid gap-4 sm:grid-cols-2" aria-labelledby="contact-h">
						<FormField
							label={m().checkout.contactName}
							id="c-name"
							error={form.errors.contact_name}
						>
							{#snippet children({ id, invalid })}
								<Input
									{id}
									bind:value={contactName}
									autocomplete="name"
									required
									aria-invalid={invalid || undefined}
								/>
							{/snippet}
						</FormField>
						<FormField
							label={m().checkout.contactPhone}
							id="c-phone"
							error={form.errors.contact_phone}
							hint={m().auth.phoneHint}
						>
							{#snippet children({ id, invalid, describedBy })}
								<Input
									{id}
									bind:value={contactPhone}
									type="tel"
									inputmode="tel"
									autocomplete="tel"
									dir="ltr"
									required
									aria-invalid={invalid || undefined}
									aria-describedby={describedBy}
								/>
							{/snippet}
						</FormField>
						<FormField
							label={m().checkout.contactEmail}
							id="c-email"
							error={form.errors.contact_email}
							class="sm:col-span-2"
						>
							{#snippet children({ id, invalid })}
								<Input
									{id}
									bind:value={contactEmail}
									type="email"
									autocomplete="email"
									dir="ltr"
									aria-invalid={invalid || undefined}
								/>
							{/snippet}
						</FormField>
					</Field.Group>
				</Card.Content>
			</Card.Root>

			{#if quote.requires_delivery}
				<Card.Root>
					<Card.Header>
						<Card.Title role="heading" aria-level={2} id="dm-h"
							>{m().delivery.chooseMethod}</Card.Title
						>
					</Card.Header>
					<Card.Content class="flex flex-col gap-6">
						{#each quote.groups.filter((g) => g.requires_delivery) as g (g.store_id)}
							{@const options = offered(g)}
							{@const choice = choices[g.store_id]}
							<Field.Set data-testid="delivery-choice">
								<Field.Legend variant="label"><bdi>{g.store_name}</bdi></Field.Legend>
								{#if !options.length}
									<Alert.Root variant="destructive"
										><Alert.Description>{m().issues.delivery_not_offered}</Alert.Description
										></Alert.Root
									>
								{:else}
									<RadioGroup.Root
										value={choice?.method ?? g.delivery_method}
										onValueChange={(v) => choose(g.store_id, v as Choice['method'])}
									>
										{#each options as o (o.method)}
											<Field.Label for="dm-{g.store_id}-{o.method}">
												<Field.Field
													orientation="horizontal"
													data-disabled={!o.available && !o.issue?.endsWith('_required')
														? true
														: undefined}
												>
													<RadioGroup.Item value={o.method} id="dm-{g.store_id}-{o.method}" />
													<Field.Content>
														<Field.Title class="flex w-full justify-between gap-3">
															<span
																>{o.method === 'PICKUP'
																	? m().delivery.pickupFromStore
																	: m().delivery.deliverToAddress}</span
															>
															<span class="tabular"
																>{o.method === 'PICKUP' || o.fee === 0
																	? m().delivery.free
																	: o.available
																		? fmt.money(o.fee)
																		: ''}</span
															>
														</Field.Title>
														<Field.Description>
															{#if o.available}
																{o.method === 'PICKUP'
																	? m().delivery.readyIn({
																			range: etaRange(
																				o.eta_min_minutes,
																				o.eta_max_minutes,
																				locale()
																			)
																		})
																	: m().delivery.eta({
																			range: etaRange(
																				o.eta_min_minutes,
																				o.eta_max_minutes,
																				locale()
																			)
																		})}
																{#if o.fee_waived}· <span class="text-success"
																		>{m().delivery.waived({
																			amount: fmt.money(o.fee_waived)
																		})}</span
																	>{:else if o.free_delivery_threshold && o.fee > 0}· {m().delivery.freeOver(
																		{
																			amount: fmt.money(o.free_delivery_threshold)
																		}
																	)}{/if}
															{:else if o.issue === 'address_required'}
																{m().delivery.pendingHint}
															{:else if o.issue && o.issue !== 'pickup_location_required'}
																{(m().issues as Record<string, string>)[o.issue] ??
																	m().delivery.unavailable}
															{/if}
														</Field.Description>
													</Field.Content>
												</Field.Field>
											</Field.Label>
										{/each}
									</RadioGroup.Root>
									{@const pickupOption = options.find((o) => o.method === 'PICKUP')}
									{#if (choice?.method ?? g.delivery_method) === 'PICKUP' && pickupOption && pickupOption.pickup_points.length > 1}
										<Field.Field>
											<Field.Label for="pp-{g.store_id}"
												>{m().delivery.choosePickupPoint}</Field.Label
											>
											<NativeSelect.Root
												id="pp-{g.store_id}"
												value={choice?.pickup_location_id ?? ''}
												onchange={(e) =>
													choose(
														g.store_id,
														'PICKUP',
														(e.currentTarget as HTMLSelectElement).value || null
													)}
											>
												<NativeSelect.Option value=""
													>{m().delivery.choosePickupPoint}</NativeSelect.Option
												>
												{#each pickupOption.pickup_points as pp (pp.id)}
													<NativeSelect.Option value={pp.id}
														>{pp.label || pp.district || pp.city} · {pp.city}</NativeSelect.Option
													>
												{/each}
											</NativeSelect.Root>
										</Field.Field>
									{:else if (choice?.method ?? g.delivery_method) === 'PICKUP' && g.delivery?.pickup_location}
										{@const pp = g.delivery.pickup_location}
										<p class="text-sm text-ink-2">
											{m().delivery.pickupPoint}: {pp.label || pp.district}
											· {fmt.list([pp.street, pp.district, pp.city])}
										</p>
									{/if}
								{/if}
							</Field.Set>
						{/each}
					</Card.Content>
				</Card.Root>
			{/if}

			<Card.Root>
				<Card.Header>
					<Card.Title role="heading" aria-level={2} id="addr-h">{m().checkout.delivery}</Card.Title>
					{#if !quote.needs_address}
						<Card.Description>{m().checkout.noAddressNeeded}</Card.Description>
					{:else if !addresses.length && !addingAddress}
						<Card.Description>{m().checkout.noAddresses}</Card.Description>
					{/if}
				</Card.Header>
				{#if quote.needs_address}
					<Card.Content>
						<Field.Group>
							{#if addresses.length}
								<Field.Set data-invalid={form.errors.address_id ? true : undefined}>
									<Field.Legend class="sr-only">{m().checkout.delivery}</Field.Legend>
									<RadioGroup.Root
										bind:value={addressId}
										aria-labelledby="addr-h"
										aria-invalid={form.errors.address_id ? true : undefined}
									>
										{#each addresses as a (a.id)}
											<Field.Label for="addr-{a.id}">
												<Field.Field orientation="horizontal">
													<RadioGroup.Item value={a.id} id="addr-{a.id}" />
													<Field.Content>
														<Field.Title><bdi>{a.label || a.recipient_name}</bdi></Field.Title>
														<Field.Description>
															{a.recipient_name} ·
															<span dir="ltr" class="tabular">{fmt.phone(a.phone)}</span>
														</Field.Description>
														<Field.Description>
															{fmt.list([
																a.street,
																a.building_number,
																a.district,
																a.city,
																fmt.region(a.region),
																a.postal_code
															])}
														</Field.Description>
													</Field.Content>
												</Field.Field>
											</Field.Label>
										{/each}
									</RadioGroup.Root>
									{#if form.errors.address_id}<Field.Error>{form.errors.address_id}</Field.Error
										>{/if}
								</Field.Set>
							{:else if form.errors.address_id}
								<Alert.Root variant="destructive"
									><Alert.Description>{form.errors.address_id}</Alert.Description></Alert.Root
								>
							{/if}

							{#if addingAddress}
								<Field.Set class="rounded-xl border border-dashed border-line-strong p-4">
									<Field.Legend>{m().account.newAddress}</Field.Legend>
									<Field.Group>
										<div class="grid gap-4 sm:grid-cols-3">
											<FormField
												label={m().account.addressLabel}
												id="na-label"
												optional
												hint={m().account.addressLabelHint}
											>
												{#snippet children({ id })}<Input
														{id}
														bind:value={newAddress.label}
													/>{/snippet}
											</FormField>
											<FormField
												label={m().account.recipient}
												id="na-recipient"
												error={addrForm.errors.recipient_name}
											>
												{#snippet children({ id, invalid })}<Input
														{id}
														bind:value={newAddress.recipient_name}
														autocomplete="name"
														aria-invalid={invalid || undefined}
													/>{/snippet}
											</FormField>
											<FormField label={m().auth.phone} id="na-phone" error={addrForm.errors.phone}>
												{#snippet children({ id, invalid })}<Input
														{id}
														bind:value={newAddress.phone}
														type="tel"
														dir="ltr"
														aria-invalid={invalid || undefined}
													/>{/snippet}
											</FormField>
										</div>
										<AddressFields
											bind:value={newAddress}
											errors={addrForm.errors}
											idPrefix="na"
											detectLocation
										/>
										<Field.Field orientation="horizontal">
											<Button type="button" onclick={saveAddress} disabled={addrForm.pending}>
												{#if addrForm.pending}<Spinner data-icon="inline-start" />{/if}{m().common
													.save}
											</Button>
											{#if addresses.length}
												<Button
													type="button"
													variant="ghost"
													onclick={() => (addingAddress = false)}>{m().common.cancel}</Button
												>
											{/if}
										</Field.Field>
									</Field.Group>
								</Field.Set>
							{:else}
								<Button
									type="button"
									variant="outline"
									class="self-start"
									onclick={() => (addingAddress = true)}
									><PlusIcon data-icon="inline-start" />{m().checkout.addAddress}</Button
								>
							{/if}
							<FormField
								label={m().delivery.instructions}
								id="d-instructions"
								hint={m().delivery.instructionsHint}
								optional
							>
								{#snippet children({ id, describedBy })}<Textarea
										{id}
										rows={2}
										maxlength={500}
										bind:value={instructions}
										aria-describedby={describedBy}
									/>{/snippet}
							</FormField>
						</Field.Group>
					</Card.Content>
				{/if}
			</Card.Root>

			<Card.Root>
				<Card.Header>
					<Card.Title role="heading" aria-level={2} id="pm-h"
						>{m().checkout.paymentMethod}</Card.Title
					>
				</Card.Header>
				<Card.Content>
					<Field.Set>
						<Field.Legend class="sr-only">{m().checkout.paymentMethod}</Field.Legend>
						<RadioGroup.Root bind:value={method} aria-labelledby="pm-h">
							{#each methods as pm (pm.value)}
								<Field.Label for="pm-{pm.value}">
									<Field.Field orientation="horizontal">
										<RadioGroup.Item value={pm.value} id="pm-{pm.value}" />
										<Field.Content><Field.Title>{pm.label}</Field.Title></Field.Content>
									</Field.Field>
								</Field.Label>
							{/each}
						</RadioGroup.Root>
						{#if mock}
							<Field.Description>{m().common.testModeNote}</Field.Description>
						{/if}
					</Field.Set>
				</Card.Content>
			</Card.Root>
		</div>

		<Card.Root class="h-fit lg:sticky lg:top-24">
			<Card.Header>
				<Card.Title role="heading" aria-level={2}>{m().checkout.summary}</Card.Title>
				<Card.Description>{m().checkout.merchantBreakdown}</Card.Description>
			</Card.Header>
			<Card.Content class="flex flex-col gap-6">
				<div class="flex flex-col gap-4">
					{#each quote.groups as g (g.merchant_id)}
						<div class="flex flex-col gap-1 text-sm" aria-busy={quoting}>
							<div class="flex justify-between gap-3 font-medium">
								<span class="truncate"><bdi>{g.store_name}</bdi></span><span class="tabular"
									>{fmt.money(g.total)}</span
								>
							</div>
							<ul class="flex flex-col gap-0.5 text-ink-3">
								{#each g.lines as l (l.cart_item_id)}
									<li class="flex justify-between gap-3">
										<span class="truncate">{l.quantity} × <bdi>{l.title}</bdi></span><span
											class="tabular">{fmt.money(l.line_total)}</span
										>
									</li>
								{/each}
								{#if g.requires_delivery && g.delivery_method !== 'NONE'}
									<li class="flex justify-between gap-3">
										<span>{m().delivery.method[g.delivery_method]}</span><span class="tabular"
											>{g.delivery_pending
												? m().delivery.pending
												: g.delivery_fee === 0
													? m().delivery.free
													: fmt.money(g.delivery_fee)}</span
										>
									</li>
								{/if}
							</ul>
							{#if g.issues.length}
								<p class="text-xs text-danger">
									{g.issues.map((c) => (m().issues as Record<string, string>)[c] ?? c).join(' · ')}
								</p>
							{/if}
						</div>
					{/each}
				</div>
				<Separator />
				<OrderSummary
					subtotal={quote.items_subtotal}
					discount={quote.discount_total}
					delivery={quote.delivery_total}
					deliveryMethod={quote.requires_delivery ? 'DELIVERY' : 'NONE'}
					deliveryPending={quote.groups.some((g) => g.delivery_pending)}
					vat={quote.vat_total}
					total={quote.total}
				/>
				{#if quote.groups.length > 1}
					<Alert.Root variant="info"
						><InfoIcon /><Alert.Description>{m().cart.separatePayments}</Alert.Description
						></Alert.Root
					>
				{/if}
				<Field.Field
					orientation="horizontal"
					data-invalid={form.errors.accept_terms ? true : undefined}
				>
					<Checkbox
						id="terms"
						bind:checked={terms}
						aria-invalid={form.errors.accept_terms ? true : undefined}
					/>
					<Field.Content>
						<Field.Label for="terms" class="font-normal">
							<span
								>{m().checkout.terms}
								<a href="/terms" target="_blank" class="underline underline-offset-2"
									>{m().footer.terms}</a
								></span
							>
						</Field.Label>
						{#if form.errors.accept_terms}<Field.Error>{form.errors.accept_terms}</Field.Error>{/if}
					</Field.Content>
				</Field.Field>
				{#if form.message}<Alert.Root variant="destructive"
						><Alert.Description>{form.message}</Alert.Description></Alert.Root
					>{/if}
			</Card.Content>
			<Card.Footer class="flex-col items-stretch gap-3">
				<Button
					type="submit"
					size="lg"
					class="w-full"
					disabled={form.pending || quoting || !quote.can_checkout}
					data-testid="place-order"
				>
					{#if form.pending}<Spinner data-icon="inline-start" />{m().checkout
							.placing}{:else}<LockIcon data-icon="inline-start" />{m().checkout.placeOrder}{/if}
				</Button>
				<p class="text-xs text-ink-3">{m().checkout.priceNote}</p>
			</Card.Footer>
		</Card.Root>
	</form>
</div>
