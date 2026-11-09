<script lang="ts">
	import { page } from '$app/state';
	import { m } from '#lib/i18n/state.svelte.js';
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

<!-- Dark band at the page bottom — scrim tokens keep it black in both themes. -->
<footer class="mt-24 bg-scrim text-on-scrim">
	<div class="container-page grid gap-12 pt-16 pb-12 md:grid-cols-[1.6fr_1fr_1fr_1fr]">
		<div class="flex max-w-sm flex-col gap-4">
			<Wordmark class="text-on-scrim" />
			<p class="text-sm leading-relaxed text-on-scrim/60">{m().footer.about}</p>
		</div>
		{#each columns as col (col.title)}
			<nav aria-label={col.title} class="flex flex-col gap-4">
				<h2 class="type-label text-on-scrim/45">{col.title}</h2>
				<ul class="flex flex-col gap-2.5 text-sm">
					{#each col.links as link (link.href)}
						<li>
							<a
								class="rounded-sm text-on-scrim/80 transition-colors hover:text-on-scrim focus-visible:ring-2 focus-visible:ring-on-scrim/60 focus-visible:outline-none"
								href={link.href}>{link.label}</a
							>
						</li>
					{/each}
				</ul>
			</nav>
		{/each}
	</div>
	<div class="border-t border-on-scrim/10">
		<div class="container-page py-6">
			<p class="type-label text-on-scrim/45">{m().footer.rights({ year })}</p>
		</div>
	</div>
</footer>
