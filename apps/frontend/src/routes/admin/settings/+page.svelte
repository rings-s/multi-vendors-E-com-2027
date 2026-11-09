<script lang="ts">
	import { invalidate } from '$app/navigation';
	import { api, call } from '#lib/api/client.js';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as RadioGroup from '#lib/components/ui/radio-group/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { FormState } from '#lib/forms.svelte.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const t = $derived(m().admin);
	let drafts = $state<Record<string, string>>({});
	let errors = $state<Record<string, string>>({});
	const forms: Record<string, FormState> = {};
	// Delivery fees get a dedicated form: the commission choice must be made explicitly.
	const keys = $derived(Object.keys(data.settings).filter((k) => k !== 'delivery'));
	type DeliveryFinance = { commission_applies_to: string; delivery_commission_rate: string };
	let delivery = $state<DeliveryFinance>({
		commission_applies_to: 'ITEMS_ONLY',
		delivery_commission_rate: '0'
	});
	const deliveryForm = new FormState();

	$effect.pre(() => {
		drafts = Object.fromEntries(
			Object.entries(data.settings).map(([k, v]) => [k, JSON.stringify(v, null, 2)])
		);
		for (const k of Object.keys(data.settings)) forms[k] ??= new FormState();
		const current = data.settings.delivery as DeliveryFinance | undefined;
		if (current)
			delivery = {
				commission_applies_to: current.commission_applies_to,
				delivery_commission_rate: String(Number(current.delivery_commission_rate))
			};
	});

	async function saveDelivery(e: SubmitEvent) {
		e.preventDefault();
		deliveryForm.reset();
		const both = delivery.commission_applies_to === 'ITEMS_AND_DELIVERY';
		const rate = both ? Number(delivery.delivery_commission_rate) : 0;
		if (both && !(rate > 0 && rate <= 100))
			return deliveryForm.fail('delivery_commission_rate', m().errors.invalidAmount);
		const res = await deliveryForm.submit(
			() =>
				call(
					api.PUT('/api/v1/admin/settings/{key}', {
						params: { path: { key: 'delivery' } },
						body: {
							commission_applies_to: delivery.commission_applies_to,
							delivery_commission_rate: String(rate)
						}
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) await invalidate('app:settings');
	}

	async function save(key: string) {
		let value: Record<string, unknown>;
		try {
			value = JSON.parse(drafts[key]);
			errors = { ...errors, [key]: '' };
		} catch {
			errors = { ...errors, [key]: t.invalidJson };
			return;
		}
		const res = await forms[key].submit(
			() =>
				call(api.PUT('/api/v1/admin/settings/{key}', { params: { path: { key } }, body: value })),
			{ success: m().common.saved }
		);
		if (res.ok) await invalidate('app:settings');
		else if (forms[key].message)
			errors = {
				...errors,
				[key]: [
					forms[key].message,
					...Object.entries(forms[key].errors).map(([f, msg]) => `${f}: ${msg}`)
				].join('\n')
			};
	}
</script>

<svelte:head><title>{t.settings} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={t.settings} />
	<Card.Root role="region" aria-labelledby="set-delivery">
		<form onsubmit={saveDelivery} novalidate class="contents">
			<Card.Header>
				<Card.Title role="heading" aria-level={2} id="set-delivery"
					>{m().delivery.adminTitle}</Card.Title
				>
				<Card.Description>{m().delivery.adminHint}</Card.Description>
				<Card.Action>
					<Button size="sm" type="submit" disabled={deliveryForm.pending}
						>{#if deliveryForm.pending}<Spinner data-icon="inline-start" />{/if}{m().common
							.save}</Button
					>
				</Card.Action>
			</Card.Header>
			<Card.Content>
				<Field.Group>
					<RadioGroup.Root bind:value={delivery.commission_applies_to}>
						{#each [['ITEMS_ONLY', m().delivery.commissionItemsOnly], ['ITEMS_AND_DELIVERY', m().delivery.commissionItemsAndDelivery]] as [value, label] (value)}
							<Field.Field orientation="horizontal">
								<RadioGroup.Item {value} id="dc-{value}" />
								<Field.Label for="dc-{value}" class="font-normal">{label}</Field.Label>
							</Field.Field>
						{/each}
					</RadioGroup.Root>
					{#if delivery.commission_applies_to === 'ITEMS_AND_DELIVERY'}
						<FormField
							label={m().delivery.deliveryRate}
							id="dc-rate"
							error={deliveryForm.errors.delivery_commission_rate}
							class="max-w-xs"
						>
							{#snippet children({ id, invalid })}<Input
									{id}
									type="number"
									min={0}
									max={100}
									step="0.5"
									inputmode="decimal"
									dir="ltr"
									bind:value={delivery.delivery_commission_rate}
									aria-invalid={invalid || undefined}
								/>{/snippet}
						</FormField>
					{/if}
					{#if deliveryForm.message}<Alert.Root variant="destructive"
							><Alert.Description>{deliveryForm.message}</Alert.Description></Alert.Root
						>{/if}
				</Field.Group>
			</Card.Content>
		</form>
	</Card.Root>
	{#each keys as key (key)}
		<Card.Root role="region" aria-labelledby="set-{key}">
			<Card.Header>
				<Card.Title role="heading" aria-level={2} id="set-{key}" dir="ltr">{key}</Card.Title>
				<Card.Action>
					<Button size="sm" onclick={() => save(key)} disabled={forms[key]?.pending}
						>{#if forms[key]?.pending}<Spinner data-icon="inline-start" />{/if}{m().common
							.save}</Button
					>
				</Card.Action>
			</Card.Header>
			<Card.Content class="flex flex-col gap-3">
				<!-- JSON editor: monospace is functional here, not decoration. -->
				<Textarea
					bind:value={drafts[key]}
					rows={Math.min(18, (drafts[key] ?? '').split('\n').length + 1)}
					class="font-mono text-xs"
					dir="ltr"
					spellcheck={false}
					aria-label="{t.settingValue}: {key}"
					aria-invalid={errors[key] ? true : undefined}
				/>
				{#if errors[key]}<Alert.Root variant="destructive"
						><Alert.Description class="whitespace-pre-line">{errors[key]}</Alert.Description
						></Alert.Root
					>{/if}
			</Card.Content>
		</Card.Root>
	{/each}
</div>
