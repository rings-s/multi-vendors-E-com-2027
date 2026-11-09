<script lang="ts">
	import * as Card from '#lib/components/ui/card/index.js';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import TestModeBadge from '#lib/components/app/TestModeBadge.svelte';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const p = $derived(data.provider);
	const t = $derived(m().admin);
	const yes = (b: boolean) => (b ? m().common.yes : m().common.no);
</script>

<svelte:head><title>{t.provider} · {t.title}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={t.provider}>
		{#snippet meta()}<div class="flex items-center gap-2">
				<span class="text-lg font-medium capitalize">{p.provider}</span
				>{#if p.is_test}<TestModeBadge />{/if}
			</div>{/snippet}
	</PageHeader>
	<section>
		<Card.Root class="h-full">
			<Card.Header>
				<Card.Title role="heading" aria-level={2}>{t.providerCapabilities}</Card.Title>
			</Card.Header>
			<Card.Content class="flex flex-col gap-4">
				<dl class="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
					<div>
						<dt class="text-ink-3">{t.supportsSplits}</dt>
						<dd>
							<StatusBadge
								status={p.supports_splits ? 'ENABLED' : 'DISABLED'}
								label={yes(p.supports_splits)}
							/>
						</dd>
					</div>
					<div>
						<dt class="text-ink-3">{t.maxMerchants}</dt>
						<dd class="tabular">{fmt.number(p.max_merchants_per_payment)}</dd>
					</div>
					<div>
						<dt class="text-ink-3">{t.platformRecipient}</dt>
						<dd>
							<StatusBadge
								status={p.platform_recipient_configured ? 'ENABLED' : 'DISABLED'}
								label={yes(p.platform_recipient_configured)}
							/>
						</dd>
					</div>
					<div>
						<dt class="text-ink-3">{t.settlementLookup}</dt>
						<dd>{yes(p.supports_settlement_lookup)}</dd>
					</div>
					<div>
						<dt class="text-ink-3">{t.chargebackEvents}</dt>
						<dd>{yes(p.supports_chargeback_events)}</dd>
					</div>
				</dl>
			</Card.Content>
		</Card.Root>
	</section>
	<section>
		<Card.Root class="h-full">
			<Card.Header>
				<Card.Title role="heading" aria-level={2}>{t.accountsByStatus}</Card.Title>
			</Card.Header>
			<Card.Content class="flex flex-col gap-4">
				<dl class="flex flex-wrap gap-6 text-sm">
					{#each Object.entries(p.merchant_accounts_by_status) as [status, count] (status)}
						<div class="flex flex-col gap-1">
							<dt><StatusBadge {status} /></dt>
							<dd class="text-xl font-medium tabular">{fmt.number(Number(count))}</dd>
						</div>
					{/each}
				</dl>
			</Card.Content>
		</Card.Root>
	</section>
	{#if p.notes.length}
		<section>
			<Card.Root class="h-full">
				<Card.Header>
					<Card.Title role="heading" aria-level={2}>{t.notes}</Card.Title>
				</Card.Header>
				<Card.Content class="flex flex-col gap-3">
					<ul class="flex list-disc flex-col gap-1 ps-5 text-sm text-ink-2">
						{#each p.notes as n (n)}<li>{n}</li>{/each}
					</ul>
				</Card.Content>
			</Card.Root>
		</section>
	{/if}
</div>
