<script lang="ts">
	import { goto } from '$app/navigation';
	import { page as appPage } from '$app/state';
	import * as Pagination from '#lib/components/ui/pagination/index.js';
	import { m, fmt } from '#lib/i18n/state.svelte.js';

	interface Props {
		total: number;
		page: number;
		pageSize: number;
		/** Query parameter that holds the page number. */
		param?: string;
		/** Called instead of navigating, for client-side lists. */
		onchange?: (page: number) => void;
	}

	let { total, page, pageSize, param = 'page', onchange }: Props = $props();
	const pages = $derived(Math.max(1, Math.ceil(total / pageSize)));

	function go(next: number) {
		if (onchange) return onchange(next);
		const url = new URL(appPage.url.href);
		if (next <= 1) url.searchParams.delete(param);
		else url.searchParams.set(param, String(next));
		void goto(url);
	}
</script>

{#if pages > 1}
	<div class="flex flex-col items-center gap-2 pt-6 sm:flex-row sm:justify-between">
		<p class="text-sm text-ink-3 tabular">
			{m().common.page({ page, pages })} · {m().common.results({ count: total })}
		</p>
		<Pagination.Root
			count={total}
			perPage={pageSize}
			{page}
			onPageChange={go}
			class="mx-0 w-auto"
			aria-label={m().ui.pagination}
		>
			{#snippet children({ pages: items, currentPage })}
				<Pagination.Content>
					<Pagination.Item>
						<Pagination.Previous label={m().common.previous} />
					</Pagination.Item>
					{#each items as item (item.key)}
						{#if item.type === 'ellipsis'}
							<Pagination.Item><Pagination.Ellipsis /></Pagination.Item>
						{:else}
							<Pagination.Item>
								<Pagination.Link page={item} isActive={currentPage === item.value}>
									{fmt.number(item.value)}
								</Pagination.Link>
							</Pagination.Item>
						{/if}
					{/each}
					<Pagination.Item>
						<Pagination.Next label={m().common.next} />
					</Pagination.Item>
				</Pagination.Content>
			{/snippet}
		</Pagination.Root>
	</div>
{/if}
