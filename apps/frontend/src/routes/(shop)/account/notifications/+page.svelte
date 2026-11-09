<script lang="ts">
	import { goto, invalidate } from '$app/navigation';
	import BellIcon from '@lucide/svelte/icons/bell';
	import CheckCheckIcon from '@lucide/svelte/icons/check-check';
	import { api, call } from '#lib/api/client.js';
	import type { Notification } from '#lib/api/types.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as Item from '#lib/components/ui/item/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const refresh = () => invalidate('app:notifications');

	async function markRead(n: Notification) {
		if (n.read_at) return;
		await action(() =>
			call(
				api.POST('/api/v1/notifications/{notification_id}/read', {
					params: { path: { notification_id: n.id } }
				})
			)
		);
		await refresh();
	}

	async function markAll() {
		await action(() => call(api.POST('/api/v1/notifications/read-all')));
		await refresh();
	}

	function link(n: Notification): string | null {
		const d = n.data as Record<string, unknown>;
		if (typeof d.order_id === 'string') return `/account/orders/${d.order_id}`;
		return null;
	}
</script>

<svelte:head><title>{m().account.notifications} · {m().brand.name}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().account.notifications}>
		{#snippet actions()}
			<Field.Field orientation="horizontal" class="w-auto">
				<Switch
					id="unread"
					checked={data.unreadOnly}
					onCheckedChange={(v) => goto(v ? '?unread=1' : '?')}
				/>
				<Field.Label for="unread" class="font-normal">{m().account.unreadOnly}</Field.Label>
			</Field.Field>
			{#if data.notifications.unread > 0}
				<Button variant="outline" onclick={markAll}
					><CheckCheckIcon data-icon="inline-start" />{m().account.markAllRead}</Button
				>
			{/if}
		{/snippet}
	</PageHeader>

	{#if data.notifications.items.length}
		<Item.Group class="gap-0 overflow-hidden rounded-2xl border border-line bg-surface">
			{#each data.notifications.items as n, i (n.id)}
				{@const href = link(n)}
				{#if i > 0}<Item.Separator class="my-0" />{/if}
				<Item.Root
					role="listitem"
					data-unread={!n.read_at || undefined}
					class="items-start gap-4 rounded-none p-5 data-unread:bg-brand-soft/30"
				>
					<Item.Media class="pt-2">
						<span
							class={cn('size-2 rounded-full', n.read_at ? 'bg-transparent' : 'bg-primary')}
							aria-hidden="true"
						></span>
					</Item.Media>
					<Item.Content class="min-w-0">
						<Item.Title><bdi>{n.title}</bdi></Item.Title>
						<Item.Description class="line-clamp-none"><bdi>{n.body}</bdi></Item.Description>
						<p class="text-xs text-ink-3">
							<time datetime={n.created_at}>{fmt.relative(n.created_at)}</time>
						</p>
					</Item.Content>
					<Item.Actions class="flex-col items-end">
						{#if href}<Button size="sm" variant="ghost" {href} onclick={() => markRead(n)}
								>{m().common.view}</Button
							>{/if}
						{#if !n.read_at}<Button size="sm" variant="ghost" onclick={() => markRead(n)}
								>{m().ui.markRead}</Button
							>{/if}
					</Item.Actions>
				</Item.Root>
			{/each}
		</Item.Group>
		<Paginator
			total={data.notifications.total}
			page={data.notifications.page}
			pageSize={data.notifications.page_size}
		/>
	{:else}
		<EmptyState icon={BellIcon} title={m().account.noNotifications} />
	{/if}
</div>
