<script lang="ts">
	import FinanceSummary from '#lib/components/app/FinanceSummary.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import QueryFilter from '#lib/components/app/QueryFilter.svelte';
	import SalesChart from '#lib/components/app/SalesChart.svelte';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head><title>{m().merchant.earnings} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-8">
	<PageHeader title={m().merchant.earnings}>
		{#snippet actions()}
			<QueryFilter
				param="days"
				value={String(data.days)}
				label={m().merchant.period}
				options={data.periods.map((d) => ({
					value: String(d),
					label: m().merchant.days({ n: d })
				}))}
			/>
		{/snippet}
	</PageHeader>
	<FinanceSummary summary={data.earnings.summary} />
	<section>
		<Card.Root class="h-full">
			<Card.Content>
				<SalesChart
					points={data.earnings.daily}
					title="{m().merchant.totalSales} · {m().merchant.days({ n: data.days })}"
				/>
			</Card.Content>
		</Card.Root>
	</section>
	<Alert.Root
		><Alert.Title>{m().merchant.settlements}</Alert.Title><Alert.Description
			>{m().merchant.settlementExplainer}</Alert.Description
		></Alert.Root
	>
</div>
