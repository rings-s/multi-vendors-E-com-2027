<script lang="ts">
	import { page } from '$app/state';
	import { m } from '#lib/i18n/state.svelte.js';
	import PrefToggles from './PrefToggles.svelte';
	import Wordmark from './Wordmark.svelte';

	const year = new Date().getFullYear();
	const user = $derived(page.data.user);

	const columns = $derived([
		{
			title: m().footer.shop,
			links: [
				{ href: '/stores', label: m().nav.stores },
				{ href: '/products', label: m().nav.products },
				{ href: '/services', label: m().nav.services },
				{ href: '/search', label: m().common.search }
			]
		},
		{
			title: m().footer.sell,
			links: [
				{ href: '/sell', label: m().footer.becomeMerchant },
				{ href: user ? '/merchant' : '/sign-in?next=/merchant', label: m().footer.merchantLogin }
			]
		},
		{
			title: m().footer.help,
			links: [
				{ href: '/account/support', label: m().footer.support },
				{ href: '/terms', label: m().footer.terms },
				{ href: '/privacy', label: m().footer.privacy }
			]
		}
	]);
</script>

<footer class="mt-24 border-t border-line bg-surface-2">
	<div
		class="container-page grid gap-x-8 gap-y-10 pt-14 pb-12 sm:grid-cols-3 lg:grid-cols-[1.7fr_1fr_1fr_1fr]"
	>
		<div class="flex max-w-sm flex-col gap-4 sm:col-span-3 lg:col-span-1">
			<Wordmark />
			<p class="text-sm leading-relaxed text-ink-2">{m().footer.about}</p>
		</div>
		{#each columns as col (col.title)}
			<nav aria-label={col.title} class="flex flex-col gap-3.5">
				<h2 class="text-sm font-semibold text-ink">{col.title}</h2>
				<ul class="flex flex-col gap-2.5 text-sm">
					{#each col.links as link (link.href)}
						<li>
							<a
								class="rounded-sm text-ink-2 underline-offset-4 transition-colors outline-none hover:text-ink hover:underline focus-visible:ring-2 focus-visible:ring-ring/60"
								href={link.href}>{link.label}</a
							>
						</li>
					{/each}
				</ul>
			</nav>
		{/each}
	</div>
	<div class="border-t border-line">
		<div
			class="container-page flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between"
		>
			<p class="text-[0.8125rem] text-ink-3">{m().footer.rights({ year })}</p>
			<div class="flex items-center gap-2 [--ind-bg:var(--card)] *:bg-surface-3">
				<PrefToggles testable={false} />
			</div>
		</div>
	</div>
</footer>
