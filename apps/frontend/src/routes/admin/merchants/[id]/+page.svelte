<script lang="ts">
	import { invalidate } from '$app/navigation';
	import RefreshCwIcon from '@lucide/svelte/icons/refresh-cw';
	import { api, call } from '#lib/api/client.js';
	import FinanceSummary from '#lib/components/app/FinanceSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { prompt } from '#lib/confirm.svelte.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	type Action = 'start_review' | 'approve' | 'reject' | 'request_info' | 'suspend' | 'reactivate';
	let { data }: PageProps = $props();
	const d = $derived(data.detail);
	const mer = $derived(d.merchant);
	const pa = $derived(d.payment_account);
	let busy = $state(false);
	const t = $derived(m().admin);

	// Mirrors the backend's allowed transitions; the backend re-validates every action.
	const ACTIONS: Record<string, Action[]> = {
		SUBMITTED: ['start_review', 'approve', 'reject', 'request_info'],
		UNDER_REVIEW: ['approve', 'reject', 'request_info'],
		APPROVED: ['suspend'],
		SUSPENDED: ['reactivate'],
		REJECTED: []
	};
	const labels: Record<Action, () => string> = {
		start_review: () => t.startReview,
		approve: () => t.approve,
		reject: () => t.reject,
		request_info: () => t.requestInfo,
		suspend: () => t.suspend,
		reactivate: () => t.reactivate
	};
	const needsReason = new Set<Action>(['reject', 'request_info', 'suspend']);
	const available = $derived(ACTIONS[mer.status] ?? []);

	async function run(a: Action) {
		let reason: string | null = null;
		reason = await prompt({
			title: labels[a](),
			label: t.actionReason,
			minLength: needsReason.has(a) ? 3 : 0,
			optional: !needsReason.has(a),
			destructive: ['reject', 'suspend'].includes(a),
			confirmLabel: labels[a]()
		});
		if (reason == null) return;
		busy = true;
		await action(
			() =>
				call(
					api.POST('/api/v1/admin/merchants/{merchant_id}/{action}', {
						params: { path: { merchant_id: mer.id, action: a } },
						body: { reason: reason || null }
					})
				),
			t.actionDone
		);
		busy = false;
		await invalidate('app:admin-merchant');
	}

	async function syncProvider() {
		busy = true;
		await action(
			() =>
				call(
					api.POST('/api/v1/admin/merchants/{merchant_id}/payment-account/sync', {
						params: { path: { merchant_id: mer.id } }
					})
				),
			m().merchant.synced
		);
		busy = false;
		await invalidate('app:admin-merchant');
	}
</script>

<svelte:head><title>{mer.business_name} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader
		title={mer.business_name}
		description={m().businessTypes[
			mer.business_type as keyof ReturnType<typeof m>['businessTypes']
		] ?? mer.business_type}
	>
		{#snippet meta()}
			<div class="flex flex-wrap items-center gap-3 text-sm text-ink-3">
				<StatusBadge status={mer.status} />
				{#if mer.store_slug}<a
						class="text-primary hover:underline"
						href="/stores/{mer.store_slug}"
						target="_blank"
						dir="ltr">/stores/{mer.store_slug}</a
					>{/if}
			</div>
		{/snippet}
		{#snippet actions()}
			{#each available as a (a)}
				<Button
					variant={a === 'approve' || a === 'reactivate'
						? 'default'
						: a === 'reject' || a === 'suspend'
							? 'destructive'
							: 'outline'}
					disabled={busy}
					onclick={() => run(a)}
					data-testid="merchant-action-{a}">{labels[a]()}</Button
				>
			{/each}
		{/snippet}
	</PageHeader>

	{#if mer.status_reason}
		<Alert.Root role="note">
			<Alert.Title>{t.actionReason}</Alert.Title>
			<Alert.Description>{mer.status_reason}</Alert.Description>
		</Alert.Root>
	{/if}

	<div class="grid gap-6 lg:grid-cols-2">
		<section>
			<Card.Root class="h-full">
				<Card.Header>
					<Card.Title role="heading" aria-level={2}>{t.business}</Card.Title>
				</Card.Header>
				<Card.Content class="flex flex-col gap-4 text-sm">
					<dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
						<dt class="text-ink-3">{t.owner}</dt>
						<dd>{mer.owner_full_name}</dd>
						<dt class="text-ink-3">{m().merchant.contactEmail}</dt>
						<dd dir="ltr" class="text-start">{mer.contact_email}</dd>
						<dt class="text-ink-3">{m().merchant.contactPhone}</dt>
						<dd dir="ltr" class="text-start tabular">{fmt.phone(mer.contact_phone)}</dd>
						<dt class="text-ink-3">{m().sell.crNumber}</dt>
						<dd class="tabular">{mer.commercial_registration_number ?? '—'}</dd>
						<dt class="text-ink-3">{m().sell.vatNumber}</dt>
						<dd class="tabular">{mer.vat_number ?? '—'}</dd>
						<dt class="text-ink-3">{m().merchant.website}</dt>
						<dd dir="ltr" class="text-start">{mer.website ?? '—'}</dd>
						<dt class="text-ink-3">{t.submitted}</dt>
						<dd>{fmt.datetime(mer.submitted_at)}</dd>
						{#each mer.addresses as a (a.id)}
							<dt class="text-ink-3">{m().merchant.address}</dt>
							<dd>
								{fmt.list([
									a.street,
									a.building_number,
									a.district,
									a.city,
									fmt.region(a.region),
									a.postal_code
								])}
							</dd>
						{/each}
					</dl>
					{#if mer.business_description}<p class="whitespace-pre-line text-ink-2">
							<bdi>{mer.business_description}</bdi>
						</p>{/if}
				</Card.Content>
			</Card.Root>
		</section>

		<section>
			<Card.Root class="h-full">
				<Card.Header>
					<Card.Title role="heading" aria-level={2}>{m().merchant.paymentAccount}</Card.Title>
					<Card.Action>
						<Button size="sm" variant="outline" onclick={syncProvider} disabled={busy}
							><RefreshCwIcon data-icon="inline-start" />{t.syncProvider}</Button
						>
					</Card.Action>
				</Card.Header>
				<Card.Content class="flex flex-col gap-4 text-sm">
					<dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
						<dt class="text-ink-3">{m().merchant.provider}</dt>
						<dd class="capitalize">
							{pa.provider}{#if pa.is_test}
								· {m().common.testMode}{/if}
						</dd>
						<dt class="text-ink-3">{m().merchant.onboardingStatus}</dt>
						<dd><StatusBadge status={pa.onboarding_status} /></dd>
						<dt class="text-ink-3">{m().merchant.payoutStatus}</dt>
						<dd><StatusBadge status={pa.payout_status} /></dd>
						<dt class="text-ink-3">{m().merchant.canAcceptPayments}</dt>
						<dd>{pa.can_accept_payments ? m().common.yes : m().common.no}</dd>
						<dt class="text-ink-3">{m().merchant.bankAccount}</dt>
						<dd dir="ltr" class="text-start tabular">{pa.bank_account?.iban_masked ?? '—'}</dd>
						<dt class="text-ink-3">{m().merchant.lastSynced}</dt>
						<dd>{fmt.datetime(pa.last_synced_at)}</dd>
					</dl>
					{#if pa.last_error}<Alert.Root variant="destructive"
							><Alert.Description>{pa.last_error}</Alert.Description></Alert.Root
						>{/if}
				</Card.Content>
			</Card.Root>
		</section>
	</div>

	<section class="flex flex-col gap-4">
		<h2 class="type-title">{t.financials}</h2>
		<FinanceSummary summary={d.financial_summary} />
	</section>

	<section>
		<Card.Root class="h-full">
			<Card.Header>
				<Card.Title role="heading" aria-level={2}>{t.verification}</Card.Title>
			</Card.Header>
			<Card.Content class="flex flex-col gap-4">
				<ol class="flex flex-col gap-3 border-s border-line ps-4">
					{#each d.verification_history as h, i (i)}
						<li class="text-sm">
							<span class="font-medium">{statusLabel(h.to_status)}</span>
							<span class="text-ink-3">· {fmt.datetime(h.created_at)}</span>{#if h.note}<p
									class="text-ink-2"
								>
									<bdi>{h.note}</bdi>
								</p>{/if}
						</li>
					{:else}
						<li class="text-sm text-ink-3">—</li>
					{/each}
				</ol>
			</Card.Content>
		</Card.Root>
	</section>
</div>
