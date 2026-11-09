<script lang="ts">
	import { invalidate } from '$app/navigation';
	import RefreshCwIcon from '@lucide/svelte/icons/refresh-cw';
	import SendIcon from '@lucide/svelte/icons/send';
	import { api, call } from '#lib/api/client.js';
	import FormField from '#lib/components/app/FormField.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import TestModeBadge from '#lib/components/app/TestModeBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { action, FormState } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const a = $derived(data.account);
	const approved = $derived(data.merchant.status === 'APPROVED');
	const started = $derived(a.onboarding_status !== 'NOT_STARTED');
	const form = new FormState();
	let busy = $state<'submit' | 'sync' | null>(null);

	const v = $state({
		beneficiary_name: '',
		iban: '',
		bank_name: '',
		website: '',
		owners_count: 1,
		signatory: 'owner' as 'owner' | 'commercial_contract' | 'power_of_attorney',
		signatory_count: 1,
		activity_license_required: false
	});

	const refresh = () =>
		Promise.all([invalidate('app:payment-account'), invalidate('app:merchant')]);

	async function start(e: SubmitEvent) {
		e.preventDefault();
		form.reset();
		const iban = v.iban.replace(/\s+/g, '').toUpperCase();
		if (!/^SA\d{2}[A-Z0-9]{20}$/.test(iban))
			return form.fail('bank_account.iban', m().merchant.ibanHint);
		const res = await form.submit(
			() =>
				call(
					api.POST('/api/v1/merchants/payment-account', {
						body: {
							bank_account: {
								beneficiary_name: v.beneficiary_name,
								iban,
								bank_name: v.bank_name || null
							},
							website: v.website,
							owners_count: Number(v.owners_count),
							signatory: v.signatory,
							signatory_count: v.signatory === 'owner' ? null : Number(v.signatory_count),
							activity_license_required: v.activity_license_required
						}
					})
				),
			{ success: m().common.saved }
		);
		if (res.ok) await refresh();
	}

	async function run(kind: 'submit' | 'sync') {
		busy = kind;
		const ok = await action(
			() =>
				call(
					kind === 'submit'
						? api.POST('/api/v1/merchants/payment-account/submit')
						: api.POST('/api/v1/merchants/payment-account/sync')
				),
			kind === 'sync' ? m().merchant.synced : m().merchant.submitted
		);
		busy = null;
		if (ok) await refresh();
	}
</script>

<svelte:head><title>{m().merchant.paymentTitle} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={m().merchant.paymentTitle} description={m().merchant.paymentIntro}>
		{#snippet meta()}{#if a.is_test}<TestModeBadge />{/if}{/snippet}
		{#snippet actions()}
			{#if started}
				<Button variant="outline" onclick={() => run('sync')} disabled={busy !== null}
					>{#if busy === 'sync'}<Spinner data-icon="inline-start" />{:else}<RefreshCwIcon
							data-icon="inline-start"
						/>{/if}{m().merchant.syncStatus}</Button
				>
				{#if ['PENDING', 'ACTION_REQUIRED', 'FAILED'].includes(a.onboarding_status)}
					<Button onclick={() => run('submit')} disabled={busy !== null}
						>{#if busy === 'submit'}<Spinner data-icon="inline-start" />{:else}<SendIcon
								class="rtl-flip"
								data-icon="inline-start"
							/>{/if}{m().merchant.submitToProvider}</Button
					>
				{/if}
			{/if}
		{/snippet}
	</PageHeader>

	<Card.Root>
		<Card.Content>
			<dl class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="payment-account-status">
				<div class="flex flex-col gap-1">
					<dt class="text-sm text-ink-3">{m().merchant.provider}</dt>
					<dd class="font-medium capitalize">{a.provider}</dd>
				</div>
				<div class="flex flex-col gap-1">
					<dt class="text-sm text-ink-3">{m().merchant.onboardingStatus}</dt>
					<dd><StatusBadge status={a.onboarding_status} /></dd>
				</div>
				<div class="flex flex-col gap-1">
					<dt class="text-sm text-ink-3">{m().merchant.payoutStatus}</dt>
					<dd><StatusBadge status={a.payout_status} /></dd>
				</div>
				<div class="flex flex-col gap-1">
					<dt class="text-sm text-ink-3">{m().merchant.canAcceptPayments}</dt>
					<dd>
						<StatusBadge
							status={a.can_accept_payments ? 'ENABLED' : 'DISABLED'}
							label={a.can_accept_payments ? m().common.yes : m().common.no}
						/>
					</dd>
				</div>
				{#if a.verification_status}<div class="flex flex-col gap-1">
						<dt class="text-sm text-ink-3">{m().merchant.verificationStatus}</dt>
						<dd><StatusBadge status={a.verification_status} /></dd>
					</div>{/if}
				<div class="flex flex-col gap-1">
					<dt class="text-sm text-ink-3">{m().merchant.attempts}</dt>
					<dd class="tabular">{fmt.number(a.attempts)}</dd>
				</div>
				<div class="flex flex-col gap-1">
					<dt class="text-sm text-ink-3">{m().merchant.lastSynced}</dt>
					<dd class="text-sm">{fmt.datetime(a.last_synced_at)}</dd>
				</div>
				{#if a.bank_account}
					<div class="flex flex-col gap-1">
						<dt class="text-sm text-ink-3">{m().merchant.bankAccount}</dt>
						<dd class="text-sm">
							<span dir="ltr" class="tabular">{a.bank_account.iban_masked}</span> · {a.bank_account
								.beneficiary_name}
						</dd>
					</div>
				{/if}
			</dl>
		</Card.Content>
	</Card.Root>

	{#if a.last_error}<Alert.Root variant="destructive"
			><Alert.Title>{m().merchant.lastError}</Alert.Title><Alert.Description
				>{a.last_error}</Alert.Description
			></Alert.Root
		>{/if}
	{#if a.reasons.length}
		<Alert.Root
			><Alert.Title>{m().merchant.providerReasons}</Alert.Title><Alert.Description
				><ul class="list-disc ps-4">
					{#each a.reasons as r (r)}<li>{r}</li>{/each}
				</ul></Alert.Description
			></Alert.Root
		>
	{/if}
	{#if a.required_documents.length || a.documents.length}
		<section>
			<Card.Root class="h-full">
				<Card.Header>
					<Card.Title role="heading" aria-level={2}>{m().merchant.requiredDocuments}</Card.Title>
				</Card.Header>
				<Card.Content>
					<Item.Group class="gap-0">
						{#each a.documents as d, i (d.document_type)}
							{#if i > 0}<Item.Separator class="my-0" />{/if}
							<Item.Root role="listitem" size="sm" class="px-0">
								<Item.Content><Item.Title>{d.document_type}</Item.Title></Item.Content>
								<Item.Actions><StatusBadge status={d.status} /></Item.Actions>
							</Item.Root>
						{/each}
						{#each a.required_documents as d, i (i)}
							{#if i > 0 || a.documents.length}<Item.Separator class="my-0" />{/if}
							<Item.Root role="listitem" size="sm" class="px-0">
								<Item.Content
									><Item.Description dir="ltr">{JSON.stringify(d)}</Item.Description></Item.Content
								>
							</Item.Root>
						{/each}
					</Item.Group>
				</Card.Content>
			</Card.Root>
		</section>
	{/if}

	{#if !started}
		{#if !approved}
			<Alert.Root><Alert.Description>{m().merchant.mustBeApproved}</Alert.Description></Alert.Root>
		{:else}
			<form onsubmit={start} novalidate>
				<Card.Root>
					<Card.Header>
						<Card.Title role="heading" aria-level={2}>{m().merchant.startOnboarding}</Card.Title>
						<Card.Description>{m().merchant.notStarted}</Card.Description>
					</Card.Header>
					<Card.Content>
						<Field.Group>
							<div class="grid gap-4 sm:grid-cols-2">
								<FormField
									label={m().merchant.beneficiaryName}
									id="pa-ben"
									error={form.errors['bank_account.beneficiary_name']}
								>
									{#snippet children({ id, invalid })}<Input
											{id}
											bind:value={v.beneficiary_name}
											aria-invalid={invalid || undefined}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().merchant.iban}
									id="pa-iban"
									error={form.errors['bank_account.iban']}
									hint={m().merchant.ibanHint}
								>
									{#snippet children({ id, invalid, describedBy })}<Input
											{id}
											dir="ltr"
											bind:value={v.iban}
											placeholder="SA00 0000 0000 0000 0000 0000"
											autocomplete="off"
											aria-invalid={invalid || undefined}
											aria-describedby={describedBy}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().merchant.bankName}
									id="pa-bank"
									optional
									error={form.errors['bank_account.bank_name']}
								>
									{#snippet children({ id })}<Input {id} bind:value={v.bank_name} />{/snippet}
								</FormField>
								<FormField label={m().merchant.website} id="pa-web" error={form.errors.website}>
									{#snippet children({ id, invalid })}<Input
											{id}
											type="url"
											dir="ltr"
											placeholder="https://"
											bind:value={v.website}
											aria-invalid={invalid || undefined}
										/>{/snippet}
								</FormField>
								<FormField
									label={m().merchant.ownersCount}
									id="pa-owners"
									error={form.errors.owners_count}
								>
									{#snippet children({ id })}<Input
											{id}
											type="number"
											min={1}
											max={100}
											bind:value={v.owners_count}
										/>{/snippet}
								</FormField>
								<FormField label={m().merchant.signatory} id="pa-sig">
									{#snippet children({ id })}
										<NativeSelect.Root {id} bind:value={v.signatory} class="w-full">
											<NativeSelect.Option value="owner"
												>{m().merchant.signatoryOwner}</NativeSelect.Option
											>
											<NativeSelect.Option value="commercial_contract"
												>{m().merchant.signatoryContract}</NativeSelect.Option
											>
											<NativeSelect.Option value="power_of_attorney"
												>{m().merchant.signatoryPoa}</NativeSelect.Option
											>
										</NativeSelect.Root>
									{/snippet}
								</FormField>
								{#if v.signatory !== 'owner'}
									<FormField
										label={m().merchant.signatoryCount}
										id="pa-sigc"
										error={form.errors.signatory_count}
									>
										{#snippet children({ id })}<Input
												{id}
												type="number"
												min={1}
												max={100}
												bind:value={v.signatory_count}
											/>{/snippet}
									</FormField>
								{/if}
							</div>
							<Field.Field orientation="horizontal">
								<Checkbox id="pa-lic" bind:checked={v.activity_license_required} />
								<Field.Label for="pa-lic" class="font-normal"
									>{m().merchant.activityLicense}</Field.Label
								>
							</Field.Field>
						</Field.Group>
					</Card.Content>
					<Card.Footer>
						<Button type="submit" disabled={form.pending}
							>{#if form.pending}<Spinner data-icon="inline-start" />{/if}{m().merchant
								.startOnboarding}</Button
						>
					</Card.Footer>
				</Card.Root>
			</form>
		{/if}
	{/if}
</div>
