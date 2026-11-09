<script lang="ts">
	import { invalidate } from '$app/navigation';
	import { page } from '$app/state';
	import UsersIcon from '@lucide/svelte/icons/users';
	import { api, call } from '#lib/api/client.js';
	import type { RoleName, UserPublic } from '#lib/api/types.js';
	import { isSuperAdmin } from '#lib/auth.js';
	import EmptyState from '#lib/components/app/EmptyState.svelte';
	import FilterBar from '#lib/components/app/FilterBar.svelte';
	import PageHeader from '#lib/components/app/PageHeader.svelte';
	import Paginator from '#lib/components/app/Paginator.svelte';
	import StatusBadge from '#lib/components/app/StatusBadge.svelte';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { prompt } from '#lib/confirm.svelte.js';
	import { action } from '#lib/forms.svelte.js';
	import { fmt, m, statusLabel } from '#lib/i18n/state.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const superAdmin = $derived(isSuperAdmin(page.data.user));
	const ROLES: RoleName[] = ['CUSTOMER', 'MERCHANT', 'ADMIN', 'SUPER_ADMIN'];
	const refresh = () => invalidate('app:admin-users');

	async function toggle(u: UserPublic, active: boolean) {
		const reason = await prompt({
			title: active ? m().admin.activate : m().admin.deactivate,
			label: m().admin.actionReason,
			minLength: 3,
			destructive: !active
		});
		if (reason == null) return;
		await action(
			() =>
				call(
					api.POST('/api/v1/admin/users/{user_id}/active', {
						params: { path: { user_id: u.id } },
						body: { is_active: active, reason }
					})
				),
			m().common.saved
		);
		await refresh();
	}

	let rolesFor = $state<UserPublic | null>(null);
	let roles = $state<RoleName[]>([]);
	async function saveRoles() {
		if (!rolesFor) return;
		const id = rolesFor.id;
		const ok = await action(
			() =>
				call(
					api.PUT('/api/v1/admin/users/{user_id}/roles', {
						params: { path: { user_id: id } },
						body: { roles }
					})
				),
			m().common.saved
		);
		if (ok) {
			rolesFor = null;
			await refresh();
		}
	}
</script>

<svelte:head><title>{m().admin.customers} · {m().admin.title}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m().admin.customers} />
	<FilterBar>
		<Field.Field class="min-w-52 flex-1">
			<Field.Label for="ac-q">{m().common.search}</Field.Label><Input
				id="ac-q"
				name="q"
				type="search"
				value={data.q}
			/>
		</Field.Field>
	</FilterBar>
	{#if data.users.items.length}
		<div class="overflow-x-auto rounded-2xl border border-line bg-surface">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{m().auth.fullName}</Table.Head>
						<Table.Head>{m().auth.email}</Table.Head>
						<Table.Head>{m().admin.roles}</Table.Head>
						<Table.Head>{m().common.date}</Table.Head>
						<Table.Head class="text-end"
							><span class="sr-only">{m().common.actions}</span></Table.Head
						>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.users.items as u (u.id)}
						<Table.Row>
							<Table.Cell class="font-medium"
								><bdi>{u.full_name}</bdi>{#if u.phone}<p
										class="text-xs text-ink-3 tabular"
										dir="ltr"
									>
										{fmt.phone(u.phone)}
									</p>{/if}</Table.Cell
							>
							<Table.Cell dir="ltr" class="text-start text-ink-2"
								>{u.email}{#if !u.email_verified}<span class="ms-1 text-xs text-warning">✕</span
									>{/if}</Table.Cell
							>
							<Table.Cell
								><div class="flex flex-wrap gap-1">
									{#each u.roles as r (r)}<StatusBadge
											status="NONE"
											label={statusLabel(r)}
										/>{/each}
								</div></Table.Cell
							>
							<Table.Cell class="text-ink-3">{fmt.date(u.created_at)}</Table.Cell>
							<Table.Cell class="text-end">
								<div class="flex justify-end gap-1">
									{#if superAdmin}<Button
											size="sm"
											variant="ghost"
											onclick={() => {
												rolesFor = u;
												roles = [...(u.roles as RoleName[])];
											}}>{m().admin.roles}</Button
										>{/if}
									<Button size="sm" variant="outline" onclick={() => toggle(u, false)}
										>{m().admin.deactivate}</Button
									>
									<Button size="sm" variant="ghost" onclick={() => toggle(u, true)}
										>{m().admin.activate}</Button
									>
								</div>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<Paginator total={data.users.total} page={data.users.page} pageSize={data.users.page_size} />
	{:else}
		<EmptyState icon={UsersIcon} title={m().catalog.emptyTitle} />
	{/if}
</div>

<Dialog.Root open={!!rolesFor} onOpenChange={(o) => !o && (rolesFor = null)}>
	<Dialog.Content>
		<Dialog.Header
			><Dialog.Title>{m().admin.roles}</Dialog.Title><Dialog.Description
				>{rolesFor?.email}</Dialog.Description
			></Dialog.Header
		>
		<Field.Set>
			<Field.Legend class="sr-only">{m().admin.roles}</Field.Legend>
			<Field.Group data-slot="checkbox-group">
				{#each ROLES as r (r)}
					<Field.Field orientation="horizontal">
						<Checkbox
							id="role-{r}"
							checked={roles.includes(r)}
							onCheckedChange={(on) => (roles = on ? [...roles, r] : roles.filter((x) => x !== r))}
						/>
						<Field.Label for="role-{r}" class="font-normal">{statusLabel(r)}</Field.Label>
					</Field.Field>
				{/each}
			</Field.Group>
		</Field.Set>
		<Dialog.Footer>
			<Button variant="ghost" onclick={() => (rolesFor = null)}>{m().common.cancel}</Button>
			<Button onclick={saveRoles} disabled={!roles.length}>{m().common.save}</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
